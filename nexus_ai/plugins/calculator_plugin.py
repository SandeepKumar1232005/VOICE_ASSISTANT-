"""
Nexus AI — Calculator Plugin (Example)
"""

from typing import Dict, Any
from nexus_ai.plugins.base_plugin import BasePlugin

class CalculatorPlugin(BasePlugin):
    def get_info(self) -> Dict[str, str]:
        return {
            "name": "Calculator Plugin",
            "description": "Performs basic math calculations safely",
            "version": "1.0",
            "author": "Nexus Core"
        }
        
    def get_capabilities(self) -> list[str]:
        return ["CALCULATE"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "CALCULATE":
            expression = params.get("expression", "")
            if not expression:
                return {"success": False, "message": "No math expression provided."}
                
            # Very simple and safe math evaluation (no eval())
            import ast
            import operator
            
            # Supported operators
            operators = {
                ast.Add: operator.add, ast.Sub: operator.sub, 
                ast.Mult: operator.mul, ast.Div: operator.truediv, 
                ast.Pow: operator.pow, ast.USub: operator.neg
            }
            
            def eval_expr(node):
                if isinstance(node, ast.Num): # <number>
                    return node.n
                elif isinstance(node, ast.BinOp): # <left> <operator> <right>
                    return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
                elif isinstance(node, ast.UnaryOp): # <operator> <operand> e.g., -1
                    return operators[type(node.op)](eval_expr(node.operand))
                else:
                    raise TypeError(node)
                    
            try:
                # Clean up natural language
                clean_expr = expression.replace("plus", "+").replace("minus", "-")\
                    .replace("times", "*").replace("divided by", "/")
                    
                result = eval_expr(ast.parse(clean_expr, mode='eval').body)
                return {
                    "success": True, 
                    "message": f"The answer to {clean_expr} is {result}.",
                    "data": {"result": result}
                }
            except Exception:
                return {"success": False, "message": f"I couldn't calculate that expression: {expression}"}
                
        return {"success": False, "message": f"Unknown action: {action}"}
