import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.simulation.environment import TieredEnvironment

class TestTieredEnvironment(unittest.TestCase):
    def test_global_state(self):
        env = TieredEnvironment()
        env.set_global("inflation", 0.05)
        self.assertEqual(env.get_observable("global.inflation"), 0.05)
        self.assertIsNone(env.get_observable("global.missing"))

    def test_local_state(self):
        env = TieredEnvironment()
        env.set_local("T001", "paving", 0.8)
        
        # Verify specific tract
        self.assertEqual(env.get_observable("local.T001.paving"), 0.8)
        
        # Verify another tract is empty/default
        self.assertIsNone(env.get_observable("local.T002.paving"))

    def test_institutional_state(self):
        env = TieredEnvironment()
        env.institutions["FEMA"] = {"budget": 1000000}
        
        self.assertEqual(env.get_observable("institutions.FEMA.budget"), 1000000)

    def test_missing_and_defaults(self):
        env = TieredEnvironment()
        # Invalid paths
        self.assertEqual(env.get_observable("invalid.path"), None)
        self.assertEqual(env.get_observable("global"), None) 
        
        # Default value
        self.assertEqual(env.get_observable("global.unknown", default=10), 10)

if __name__ == '__main__':
    unittest.main()
