import subprocess
import unittest
from unittest.mock import patch
from runner.evaluator import evaluate, HarnessError

class EvaluatorContract(unittest.TestCase):
    def test_accept_reject_budget(self):
        r=evaluate(b'\x51');self.assertTrue(r.success);self.assertEqual(r.stack,[])
        self.assertEqual(evaluate(b'\x00').classification,'reject')
        self.assertEqual(evaluate(b'\x51',budget=0).classification,'budget')
    def test_failures_are_not_rejections(self):
        with self.assertRaises(HarnessError):evaluate(b'',binary='/nonexistent/gsr-bin')
        for process in (subprocess.CompletedProcess([],1,'','process error'),
                        subprocess.CompletedProcess([],0,'bad JSON',''),
                        subprocess.CompletedProcess([],0,'{}',''),
                        subprocess.CompletedProcess([],0,'{"protocol":true,"context":"standalone","sigversion":"tapscript_v2","success":true,"error":null,"varops-budget-remaining":0,"stack-after":[]}','')):
            with patch('runner.evaluator.subprocess.run',return_value=process):
                with self.assertRaises(HarnessError):evaluate(b'')
        with patch('runner.evaluator.subprocess.run',side_effect=subprocess.TimeoutExpired('test',1)):
            with self.assertRaises(HarnessError):evaluate(b'')
