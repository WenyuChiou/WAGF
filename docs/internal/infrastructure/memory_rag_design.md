# Memory System & RAG Tool Design Document

## 設計目標

將認知科學的記憶分層與 RAG 系統整合到 `governed_broker_framework`。

---

## 1. 目錄結構

```
broker/
├── memory/
│   ├── __init__.py
│   ├── memory_types.py       # 記憶類型定義
│   ├── working_memory.py     # 工作記憶 (TTL + 容量限制)
│   ├── episodic_memory.py    # 情景記憶 (SQLite + Vector)
│   ├── memory_manager.py     # 記憶管理器 (consolidation)
│   └── memory_tool.py        # Tool 封裝
├── rag/
│   ├── __init__.py
│   ├── document_processor.py # Markdown 切分
│   ├── retriever.py          # 向量檢索 (MQE, HyDE)
│   ├── knowledge_base.py     # 知識庫管理
│   └── rag_tool.py           # Tool 封裝
└── context_builder.py        # 整合記憶到上下文 (已存在)
```

---

## 2. Memory System 核心類

### 2.1 memory_types.py

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"  # 未來擴展

@dataclass
class MemoryItem:
    """單一記憶項目"""
    id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5  # 0-1
    embedding: Optional[List[float]] = None
    metadata: dict = field(default_factory=dict)
    ttl_seconds: Optional[int] = None  # 工作記憶用
    
    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds

@dataclass
class FloodEvent:
    """洪水事件記憶"""
    year: int
    damage: float
    action_taken: str
    outcome: str

@dataclass
class DecisionMemory:
    """決策記憶"""
    year: int
    context: dict
    decision: str
    reasoning: str
    result: str
```

### 2.2 working_memory.py

```python
from typing import List, Optional
from datetime import datetime
from .memory_types import MemoryItem
import threading

class WorkingMemory:
    """
    工作記憶 - 短期、有限容量、TTL 過期機制
    
    特點:
    - 使用 Python List 在內存中存儲
    - 容量限制 (默認 10 項)
    - TTL 過期機制 (默認 300 秒)
    - 線程安全
    """
    
    DEFAULT_TTL = 300  # 5 分鐘
    DEFAULT_CAPACITY = 10
    
    def __init__(
        self, 
        capacity: int = DEFAULT_CAPACITY,
        default_ttl: int = DEFAULT_TTL
    ):
        self._items: List[MemoryItem] = []
        self.capacity = capacity
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
    
    def add(
        self, 
        content: str, 
        importance: float = 0.5,
        ttl_seconds: Optional[int] = None,
        metadata: dict = None
    ) -> MemoryItem:
        """
        添加記憶項目
        
        Args:
            content: 記憶內容
            importance: 重要性 (0-1)，影響 consolidation
            ttl_seconds: 過期時間，None 使用默認
            metadata: 額外元數據
        """
        with self._lock:
            # 清理過期項目
            self._cleanup_expired()
            
            # 容量檢查
            if len(self._items) >= self.capacity:
                # 移除最舊的低重要性項目
                self._items.sort(key=lambda x: (x.importance, x.timestamp))
                self._items.pop(0)
            
            item = MemoryItem(
                id=f"wm_{datetime.now().timestamp()}",
                content=content,
                importance=importance,
                ttl_seconds=ttl_seconds or self.default_ttl,
                metadata=metadata or {}
            )
            self._items.append(item)
            return item
    
    def retrieve(
        self, 
        query: Optional[str] = None, 
        top_k: int = 5
    ) -> List[MemoryItem]:
        """
        檢索記憶 (按 recency + importance 排序)
        """
        with self._lock:
            self._cleanup_expired()
            
            # Score: 時間近因性 + 重要性
            def score(item: MemoryItem) -> float:
                recency = 1.0 / (1 + (datetime.now() - item.timestamp).total_seconds())
                return recency * 0.6 + item.importance * 0.4
            
            sorted_items = sorted(self._items, key=score, reverse=True)
            return sorted_items[:top_k]
    
    def _cleanup_expired(self):
        """移除過期項目"""
        self._items = [item for item in self._items if not item.is_expired()]
    
    def get_high_importance(self, threshold: float = 0.7) -> List[MemoryItem]:
        """獲取高重要性項目 (用於 consolidation)"""
        with self._lock:
            return [item for item in self._items if item.importance >= threshold]
    
    def clear(self):
        """清空工作記憶"""
        with self._lock:
            self._items.clear()
```

### 2.3 episodic_memory.py

```python
from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3
from .memory_types import MemoryItem

class EpisodicMemory:
    """
    情景記憶 - 長期、大容量、向量檢索
    
    特點:
    - SQLite 存儲元數據
    - Vector DB 存儲向量 (Qdrant 接口模擬)
    - 檢索考慮 Recency + Relevance
    """
    
    # 評分公式: (相似度 * 時間衰減) * (0.8 + 重要性 * 0.4)
    DECAY_RATE = 0.95  # 每年衰減
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._init_db()
        self._vector_store: Dict[str, List[float]] = {}  # Mock vector store
    
    def _init_db(self):
        """初始化 SQLite 數據庫"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT,
                timestamp TEXT,
                importance REAL,
                metadata TEXT
            )
        """)
        self.conn.commit()
    
    def add(
        self, 
        content: str, 
        importance: float = 0.5,
        embedding: Optional[List[float]] = None,
        metadata: dict = None
    ) -> MemoryItem:
        """添加情景記憶"""
        item = MemoryItem(
            id=f"em_{datetime.now().timestamp()}",
            content=content,
            importance=importance,
            embedding=embedding,
            metadata=metadata or {}
        )
        
        # SQLite 存儲元數據
        self.conn.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?)",
            (item.id, item.content, item.timestamp.isoformat(), 
             item.importance, str(item.metadata))
        )
        self.conn.commit()
        
        # Vector store (mock)
        if embedding:
            self._vector_store[item.id] = embedding
        
        return item
    
    def retrieve(
        self, 
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        time_window_years: Optional[int] = None
    ) -> List[MemoryItem]:
        """
        檢索情景記憶
        
        評分公式: (相似度 * 時間衰減) * (0.8 + 重要性 * 0.4)
        """
        cursor = self.conn.execute("SELECT * FROM memories")
        rows = cursor.fetchall()
        
        scored_items = []
        now = datetime.now()
        
        for row in rows:
            id_, content, timestamp_str, importance, metadata_str = row
            timestamp = datetime.fromisoformat(timestamp_str)
            
            # 時間過濾
            if time_window_years:
                years_ago = (now - timestamp).days / 365
                if years_ago > time_window_years:
                    continue
            
            # 計算分數
            # 相似度 (mock: 隨機或固定)
            similarity = self._compute_similarity(id_, query_embedding)
            
            # 時間衰減
            years_passed = (now - timestamp).days / 365
            time_decay = self.DECAY_RATE ** years_passed
            
            # 評分公式
            score = (similarity * time_decay) * (0.8 + importance * 0.4)
            
            item = MemoryItem(
                id=id_,
                content=content,
                timestamp=timestamp,
                importance=importance,
                embedding=self._vector_store.get(id_),
                metadata=eval(metadata_str) if metadata_str else {}
            )
            scored_items.append((score, item))
        
        # 排序並返回 top_k
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_items[:top_k]]
    
    def _compute_similarity(
        self, 
        item_id: str, 
        query_embedding: Optional[List[float]]
    ) -> float:
        """
        計算向量相似度
        
        TODO: 替換為真實向量運算
        """
        if query_embedding is None or item_id not in self._vector_store:
            return 0.5  # Mock: 中等相似度
        
        # Mock: 簡單點積 (實際使用 cosine similarity)
        item_embedding = self._vector_store[item_id]
        dot = sum(a * b for a, b in zip(query_embedding, item_embedding))
        return min(1.0, max(0.0, dot))
```

### 2.4 memory_manager.py

```python
from typing import List, Optional
from .working_memory import WorkingMemory
from .episodic_memory import EpisodicMemory
from .memory_types import MemoryItem

class MemoryManager:
    """
    記憶管理器 - 管理工作記憶和情景記憶
    
    職責:
    - 統一記憶存取接口
    - 記憶整合 (consolidation): 工作記憶 → 情景記憶
    - 記憶檢索 (優先工作記憶，補充情景記憶)
    """
    
    CONSOLIDATION_IMPORTANCE_THRESHOLD = 0.7
    
    def __init__(
        self,
        working_memory: Optional[WorkingMemory] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
        embedding_fn=None  # 嵌入函數
    ):
        self.working_memory = working_memory or WorkingMemory()
        self.episodic_memory = episodic_memory or EpisodicMemory()
        self.embedding_fn = embedding_fn or self._mock_embedding
    
    def add(
        self, 
        content: str, 
        importance: float = 0.5,
        to_episodic: bool = False
    ) -> MemoryItem:
        """
        添加記憶
        
        Args:
            content: 記憶內容
            importance: 重要性
            to_episodic: 直接添加到情景記憶
        """
        if to_episodic:
            embedding = self.embedding_fn(content)
            return self.episodic_memory.add(content, importance, embedding)
        else:
            return self.working_memory.add(content, importance)
    
    def retrieve(
        self, 
        query: Optional[str] = None,
        top_k: int = 5,
        include_episodic: bool = True
    ) -> List[MemoryItem]:
        """
        檢索記憶
        
        優先工作記憶，不足時補充情景記憶
        """
        # 工作記憶
        working_items = self.working_memory.retrieve(query, top_k)
        
        if len(working_items) >= top_k or not include_episodic:
            return working_items
        
        # 補充情景記憶
        remaining = top_k - len(working_items)
        query_embedding = self.embedding_fn(query) if query else None
        episodic_items = self.episodic_memory.retrieve(query_embedding, remaining)
        
        return working_items + episodic_items
    
    def consolidate_memories(self) -> int:
        """
        記憶整合: 將高重要性工作記憶轉存為情景記憶
        
        Returns:
            整合的記憶項目數量
        """
        high_importance = self.working_memory.get_high_importance(
            self.CONSOLIDATION_IMPORTANCE_THRESHOLD
        )
        
        count = 0
        for item in high_importance:
            embedding = self.embedding_fn(item.content)
            self.episodic_memory.add(
                content=item.content,
                importance=item.importance,
                embedding=embedding,
                metadata=item.metadata
            )
            count += 1
        
        return count
    
    def _mock_embedding(self, text: str) -> List[float]:
        """Mock 嵌入函數 (實際使用 OpenAI/HuggingFace)"""
        import hashlib
        # 簡單 hash 產生固定長度 "向量"
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        return [b / 255.0 for b in hash_bytes]  # 16 維向量
```

---

## 3. RAG System 核心類

### 3.1 document_processor.py

```python
from typing import List, Tuple
from dataclasses import dataclass
import re

@dataclass
class DocumentChunk:
    """文檔塊"""
    content: str
    heading: str
    level: int  # 標題層級 (1-6)
    source: str
    chunk_index: int

class DocumentProcessor:
    """
    文檔處理器 - Markdown 語義切分
    
    基於 Markdown 標題 (#) 進行智能切分
    """
    
    MAX_CHUNK_SIZE = 1000  # 最大字符數
    
    def process(self, markdown_text: str, source: str = "") -> List[DocumentChunk]:
        """
        處理 Markdown 文檔
        
        Args:
            markdown_text: Markdown 格式文本
            source: 來源文件名
            
        Returns:
            文檔塊列表
        """
        chunks = []
        current_heading = "Introduction"
        current_level = 0
        current_content = []
        chunk_index = 0
        
        for line in markdown_text.split('\n'):
            # 檢測標題
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # 保存前一個塊
                if current_content:
                    chunks.append(DocumentChunk(
                        content='\n'.join(current_content),
                        heading=current_heading,
                        level=current_level,
                        source=source,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1
                
                # 新標題
                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2)
                current_content = []
            else:
                current_content.append(line)
                
                # 超過最大大小時切分
                if len('\n'.join(current_content)) > self.MAX_CHUNK_SIZE:
                    chunks.append(DocumentChunk(
                        content='\n'.join(current_content),
                        heading=current_heading,
                        level=current_level,
                        source=source,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1
                    current_content = []
        
        # 最後一個塊
        if current_content:
            chunks.append(DocumentChunk(
                content='\n'.join(current_content),
                heading=current_heading,
                level=current_level,
                source=source,
                chunk_index=chunk_index
            ))
        
        return chunks
    
    def convert_to_markdown(self, file_path: str) -> str:
        """
        將文件轉換為 Markdown
        
        TODO: 整合 MarkItDown 庫
        """
        # Mock: 直接讀取
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ""
```

### 3.2 retriever.py

```python
from typing import List, Optional, Dict
from dataclasses import dataclass
from .document_processor import DocumentChunk

@dataclass
class SearchResult:
    """檢索結果"""
    chunk: DocumentChunk
    score: float
    query_used: str

class Retriever:
    """
    RAG 檢索器 - 支援高級檢索策略
    
    策略:
    - MQE (Multi-Query Expansion): 擴展多個查詢
    - HyDE (Hypothetical Document Embedding): 假設性文檔嵌入
    """
    
    def __init__(self, embedding_fn=None):
        self.embedding_fn = embedding_fn or self._mock_embedding
        self.index: Dict[str, tuple] = {}  # chunk_id -> (chunk, embedding)
    
    def index_documents(self, chunks: List[DocumentChunk]):
        """索引文檔塊"""
        for i, chunk in enumerate(chunks):
            chunk_id = f"{chunk.source}_{chunk.chunk_index}"
            embedding = self.embedding_fn(chunk.content)
            self.index[chunk_id] = (chunk, embedding)
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        use_mqe: bool = True,
        use_hyde: bool = False
    ) -> List[SearchResult]:
        """
        檢索相關文檔塊
        
        Args:
            query: 查詢文本
            top_k: 返回數量
            use_mqe: 使用多查詢擴展
            use_hyde: 使用假設性文檔嵌入
        """
        queries = [query]
        
        # MQE: 擴展查詢
        if use_mqe:
            queries.extend(self._expand_queries(query))
        
        # HyDE: 生成假設文檔
        if use_hyde:
            hypothetical_doc = self._generate_hypothetical_doc(query)
            queries.append(hypothetical_doc)
        
        # 檢索每個查詢
        all_results = []
        for q in queries:
            results = self._basic_search(q, top_k * 2)  # 過採樣
            all_results.extend(results)
        
        # 去重 + 排序
        seen = set()
        unique_results = []
        for result in sorted(all_results, key=lambda x: x.score, reverse=True):
            chunk_id = f"{result.chunk.source}_{result.chunk.chunk_index}"
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique_results.append(result)
        
        return unique_results[:top_k]
    
    def _basic_search(self, query: str, top_k: int) -> List[SearchResult]:
        """基本向量搜索"""
        query_embedding = self.embedding_fn(query)
        
        scores = []
        for chunk_id, (chunk, embedding) in self.index.items():
            score = self._cosine_similarity(query_embedding, embedding)
            scores.append(SearchResult(chunk=chunk, score=score, query_used=query))
        
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:top_k]
    
    def _expand_queries(self, query: str) -> List[str]:
        """
        MQE: 多查詢擴展
        
        TODO: 使用 LLM 生成多個查詢變體
        """
        # Mock: 簡單變體
        return [
            f"What is {query}?",
            f"Explain {query}",
            f"Details about {query}"
        ]
    
    def _generate_hypothetical_doc(self, query: str) -> str:
        """
        HyDE: 生成假設性文檔
        
        TODO: 使用 LLM 生成假設答案
        """
        return f"Answer to '{query}': This is a hypothetical document..."
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """計算餘弦相似度"""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    def _mock_embedding(self, text: str) -> List[float]:
        """Mock 嵌入函數"""
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        return [b / 255.0 for b in hash_obj.digest()]
```

---

## 4. Tool 封裝

### 4.1 memory_tool.py

```python
from typing import Dict, Any

class MemoryTool:
    """
    記憶工具 - Everything is a Tool
    """
    
    name = "memory"
    description = "Store and retrieve agent memories"
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
    
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        統一接口
        
        params:
            action: "add" | "retrieve" | "consolidate"
            content: str (for add)
            query: str (for retrieve)
            importance: float (optional)
        """
        action = params.get("action", "retrieve")
        
        if action == "add":
            item = self.memory_manager.add(
                content=params.get("content", ""),
                importance=params.get("importance", 0.5)
            )
            return {"status": "added", "id": item.id}
        
        elif action == "retrieve":
            items = self.memory_manager.retrieve(
                query=params.get("query"),
                top_k=params.get("top_k", 5)
            )
            return {
                "status": "retrieved",
                "memories": [{"content": i.content, "importance": i.importance} for i in items]
            }
        
        elif action == "consolidate":
            count = self.memory_manager.consolidate_memories()
            return {"status": "consolidated", "count": count}
        
        return {"status": "error", "message": "Unknown action"}
```

### 4.2 rag_tool.py

```python
from typing import Dict, Any, List

class RAGTool:
    """
    RAG 工具 - Everything is a Tool
    """
    
    name = "rag"
    description = "Retrieve relevant documents from knowledge base"
    
    def __init__(self, retriever, document_processor):
        self.retriever = retriever
        self.document_processor = document_processor
    
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        統一接口
        
        params:
            action: "search" | "index"
            query: str (for search)
            documents: List[str] (for index)
        """
        action = params.get("action", "search")
        
        if action == "search":
            results = self.retriever.search(
                query=params.get("query", ""),
                top_k=params.get("top_k", 5),
                use_mqe=params.get("use_mqe", True),
                use_hyde=params.get("use_hyde", False)
            )
            return {
                "status": "success",
                "results": [
                    {"content": r.chunk.content, "heading": r.chunk.heading, "score": r.score}
                    for r in results
                ]
            }
        
        elif action == "index":
            docs = params.get("documents", [])
            total_chunks = 0
            for doc in docs:
                chunks = self.document_processor.process(doc)
                self.retriever.index_documents(chunks)
                total_chunks += len(chunks)
            return {"status": "indexed", "total_chunks": total_chunks}
        
        return {"status": "error", "message": "Unknown action"}
```

---

## 5. 整合到 governed_broker_framework

### 5.1 修改 context_builder.py

```python
# 在 ContextBuilder 中添加記憶整合

class EnhancedContextBuilder(ContextBuilder):
    def __init__(
        self,
        state_provider: Any,
        prompt_template: str,
        memory_manager: MemoryManager,  # NEW
        rag_tool: RAGTool  # NEW
    ):
        self.memory_manager = memory_manager
        self.rag_tool = rag_tool
        # ...
    
    def build(self, agent_id: str, ...) -> Dict[str, Any]:
        context = super().build(agent_id, ...)
        
        # 添加相關記憶
        memories = self.memory_manager.retrieve(query=context.get("flood_status"), top_k=3)
        context["relevant_memories"] = [m.content for m in memories]
        
        # RAG 查詢 (如有政策問題)
        if "policy" in context:
            rag_results = self.rag_tool.run({"action": "search", "query": context["policy"]})
            context["policy_knowledge"] = rag_results.get("results", [])[:2]
        
        return context
```

---

## 6. 依賴

```
# requirements.txt 添加
qdrant-client>=1.7.0  # 向量庫 (可選，當前 mock)
pydantic>=2.0        # 數據驗證
markitdown>=0.1.0    # 文檔解析 (可選)
```
