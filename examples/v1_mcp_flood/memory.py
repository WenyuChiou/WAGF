"""
Flood Adaptation Memory Manager
動態記憶更新邏輯
"""
import random
from typing import List

# 預定義歷史事件 (對齊 LLMABMPMT-Final.py 的 PAST_EVENTS)
PAST_EVENTS = [
    "A few households in the area elevated their homes before recent floods.",
    "You recall a conversation with a neighbor who lost everything in a past flood.",
    "The local news recently covered flood preparedness tips.",
    "You remember seeing insurance advertisements promising fast payouts.",
    "A community meeting discussed the increasing flood risks in the region."
]

# 記憶窗口大小
MEMORY_WINDOW = 5

# 隨機回憶概率
RANDOM_MEMORY_RECALL_CHANCE = 0.2


class MemoryManager:
    """
    管理 agent 記憶的類
    """
    
    def __init__(self, window_size: int = MEMORY_WINDOW):
        self.window_size = window_size
    
    def add_event(self, memory: List[str], event: str) -> List[str]:
        """添加新事件到記憶"""
        memory.append(event)
        # 保持記憶窗口大小
        return memory[-self.window_size:]
    
    def add_flood_memory(self, memory: List[str], year: int, flood_occurred: bool) -> List[str]:
        """添加洪水相關記憶"""
        if flood_occurred:
            event = f"Year {year}: A flood occurred and caused damage to many homes in the area."
        else:
            event = f"Year {year}: No flood occurred this year."
        return self.add_event(memory, event)
    
    def add_decision_memory(self, memory: List[str], year: int, decision: str) -> List[str]:
        """添加決策記憶"""
        decision_texts = {
            "1": f"Year {year}: You purchased flood insurance for protection.",
            "2": f"Year {year}: You elevated your house to reduce flood risk.",
            "3": f"Year {year}: You decided to relocate to a safer area.",
            "4": f"Year {year}: You chose to take no action this year."
        }
        event = decision_texts.get(decision, f"Year {year}: You made a decision.")
        return self.add_event(memory, event)
    
    def maybe_add_random_recall(self, memory: List[str], seed: int = None) -> List[str]:
        """可能添加隨機歷史回憶"""
        if seed is not None:
            random.seed(seed)
        
        if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
            past_event = random.choice(PAST_EVENTS)
            event = f"Suddenly recalled: '{past_event}'."
            return self.add_event(memory, event)
        return memory
    
    def format_memory_for_prompt(self, memory: List[str]) -> str:
        """格式化記憶用於 prompt"""
        if not memory:
            return "- No significant memories to recall."
        return "\n".join(f"- {m}" for m in memory)


def update_memory_after_step(
    memory: List[str],
    year: int,
    flood_occurred: bool,
    decision: str,
    seed: int = None
) -> List[str]:
    """
    完整的年度記憶更新邏輯
    對齊 LLMABMPMT-Final.py 的記憶更新流程
    """
    manager = MemoryManager()
    
    # 1. 添加洪水狀態記憶
    memory = manager.add_flood_memory(memory, year, flood_occurred)
    
    # 2. 添加決策記憶
    memory = manager.add_decision_memory(memory, year, decision)
    
    # 3. 可能添加隨機回憶
    memory = manager.maybe_add_random_recall(memory, seed)
    
    return memory
