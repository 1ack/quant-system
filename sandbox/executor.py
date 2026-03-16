"""
策略代码沙箱执行器

使用 RestrictedPython 实现安全的策略代码执行
防止恶意代码执行（文件操作、网络请求、系统调用等）
"""
import types
import sys
from pathlib import Path
import RestrictedPython
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import safe_builtins, guarded_iter_unpack_sequence, guarded_unpack_sequence
from loguru import logger

# 添加项目根目录到 Python 路径（确保可以导入 strategy 等模块）
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class SandboxExecutor:
    """策略代码沙箱执行器"""
    
    # 允许的全局函数
    ALLOWED_FUNCTIONS = {
        'len': len,
        'range': range,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'min': min,
        'max': max,
        'sum': sum,
        'abs': abs,
        'round': round,
        'pow': pow,
        'zip': zip,
        'enumerate': enumerate,
        'sorted': sorted,
        'reversed': reversed,
        'all': all,
        'any': any,
    }
    
    # 允许的模块
    # 空列表表示允许完整导入，非空列表表示只允许导入指定属性
    ALLOWED_MODULES = {
        'math': ['sin', 'cos', 'tan', 'exp', 'log', 'log10', 'sqrt', 'pi', 'e'],
        'datetime': [],  # 允许完整导入
        'pandas': [],    # 允许完整导入（策略需要 DataFrame 等）
        'strategy': [],  # 允许导入策略基类模块
    }
    
    def __init__(self):
        self._setup_safe_environment()
        self._preload_modules()
    
    def _preload_modules(self):
        """预加载受信任的内部模块"""
        try:
            # 预加载策略基类模块
            import strategy.base
            self._trusted_modules = {
                'strategy.base': strategy.base,
                'strategy': strategy,
            }
        except Exception as e:
            logger.warning(f"Failed to preload strategy module: {e}")
            self._trusted_modules = {}
    
    def _setup_safe_environment(self):
        """设置安全执行环境"""
        # 创建安全的 builtins
        self.safe_builtins = dict(safe_builtins)
        
        # 添加允许的函数
        self.safe_builtins.update(self.ALLOWED_FUNCTIONS)
        
        # 添加安全的 print
        self.safe_builtins['_print_'] = self._safe_print
        self.safe_builtins['print'] = self._safe_print
        
        # 添加 Python 2/3 兼容性变量和 RestrictedPython 需要的特殊变量
        self.safe_builtins['__metaclass__'] = type
        self.safe_builtins['__file__'] = '<sandbox>'
        self.safe_builtins['__name__'] = 'sandbox_strategy'
        self.safe_builtins['__doc__'] = None
        self.safe_builtins['_getiter_'] = lambda x: x
        self.safe_builtins['_getitem_'] = lambda x, y: x[y]
        self.safe_builtins['_write_'] = lambda x: x
        self.safe_builtins['_read_'] = lambda x: x
        self.safe_builtins['_delattr_'] = lambda x, y: x.__delattr__(y)
        self.safe_builtins['_getattr_'] = lambda x, y: getattr(x, y)
        self.safe_builtins['_inplacevar_'] = lambda op, x, y: x
        
        # 禁止危险的内置函数（但保留 __import__ 并替换为受限版本）
        dangerous = ['eval', 'exec', 'compile', 'open', 'file', 
                     'input', 'raw_input', 'reload', 'globals', 'locals', 'vars']
        for name in dangerous:
            if name in self.safe_builtins:
                del self.safe_builtins[name]
        
        # 替换 __import__ 为受限版本
        self.safe_builtins['__import__'] = self._import_restricted
        
        # 添加安全的迭代工具
        self.safe_builtins['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
        self.safe_builtins['_unpack_sequence_'] = guarded_unpack_sequence
    
    def _safe_print(self, *args, **kwargs):
        """安全的打印函数"""
        try:
            msg = ' '.join(str(arg) for arg in args)
            logger.info(f"[Strategy] {msg}")
        except Exception as e:
            logger.warning(f"Print error: {e}")
    
    def _import_restricted(self, name, globals=None, locals=None, fromlist=None, level=0):
        """受限的导入函数"""
        # 检查是否是预加载的可信模块
        if name in self._trusted_modules:
            return self._trusted_modules[name]
        
        # 提取模块根名称（处理 pandas.core 这样的子模块）
        root_name = name.split('.')[0]
        
        if root_name not in self.ALLOWED_MODULES:
            raise ImportError(f"Module '{name}' is not allowed in sandbox")
        
        allowed_attrs = set(self.ALLOWED_MODULES.get(root_name, []))
        
        # 如果是完整模块导入（如 import pandas as pd），返回完整模块
        if not fromlist and len(allowed_attrs) == 0:
            # 允许完整导入的模块
            return __import__(name, globals, locals, fromlist or [], level)
        
        # 只允许导入指定的子模块
        module = __import__(name, globals, locals, fromlist or [], level)
        
        if fromlist:
            # 导入特定属性
            result = types.ModuleType(name)
            for attr in fromlist:
                if attr in allowed_attrs and hasattr(module, attr):
                    setattr(result, attr, getattr(module, attr))
            return result
        else:
            # 只返回模块的允许属性
            result = types.ModuleType(name)
            for attr in allowed_attrs:
                if hasattr(module, attr):
                    setattr(result, attr, getattr(module, attr))
            return result
    
    def execute(self, code: str, context: dict = None) -> dict:
        """
        在沙箱中执行策略代码
        
        Args:
            code: Python 策略代码
            context: 执行上下文（提供 BaseStrategy, Signal, SignalType 等）
        
        Returns:
            dict: 执行结果，包含 strategy_class 或 error
        """
        try:
            # 编译受限代码
            byte_code = compile_restricted(code, '<strategy>', 'exec')
            
            # 准备执行环境
            exec_globals = {
                '__builtins__': self.safe_builtins,
                '__import__': self._import_restricted,
                '__name__': '__main__',
                '__doc__': None,
                '__package__': None,
                '__file__': '<sandbox>',
                '__loader__': None,
                '__spec__': None,
                '__annotations__': {},
                # RestrictedPython 特殊变量
                '_write_': lambda x: x,
                '_read_': lambda x: x,
                '_getiter_': lambda x: x,
                '_getitem_': lambda x, y: x[y],
                '_getattr_': lambda x, y: getattr(x, y),
                '_delattr_': lambda x, y: x.__delattr__(y),
                '_inplacevar_': lambda op, x, y: x,
            }
            
            # 添加上下文（策略基类、信号类等）
            if context:
                exec_globals.update(context)
            
            # 执行代码
            exec(byte_code, exec_globals)
            
            # 查找策略类（排除 BaseStrategy 基类）
            strategy_class = None
            strategy_name = None
            for name, obj in exec_globals.items():
                if isinstance(obj, type) and name.endswith('Strategy') and name != 'BaseStrategy':
                    strategy_class = obj
                    strategy_name = name
                    logger.info(f"Found strategy class: {name}")
                    break
            
            if not strategy_class:
                # 调试：打印所有类
                all_classes = [name for name, obj in exec_globals.items() if isinstance(obj, type)]
                logger.warning(f"No strategy class found. All classes: {all_classes}")
                return {
                    'success': False,
                    'error': '未找到策略类（类名需以 Strategy 结尾）'
                }
            
            return {
                'success': True,
                'strategy_class': strategy_class,
                'globals': exec_globals
            }
            
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate(self, code: str) -> dict:
        """
        验证代码安全性（不执行，仅检查）
        
        Args:
            code: Python 策略代码
        
        Returns:
            dict: 验证结果
        """
        try:
            # 尝试编译
            byte_code = compile_restricted(code, '<strategy>', 'exec')
            
            # 检查危险关键字
            dangerous_keywords = ['import', 'from', '__', 'exec', 'eval', 'open', 'file']
            lines = code.split('\n')
            warnings = []
            
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                
                # 检查危险模式
                if 'import' in stripped and 'math' not in stripped and 'datetime' not in stripped:
                    warnings.append(f"第{i}行：检测到导入语句，可能不安全")
                if '__' in stripped and 'class' not in stripped:
                    warnings.append(f"第{i}行：检测到双下划线，可能访问内部属性")
                if any(kw in stripped for kw in ['exec(', 'eval(', 'open(', 'file(']):
                    warnings.append(f"第{i}行：检测到危险函数调用")
            
            return {
                'valid': True,
                'warnings': warnings,
                'compiled': True
            }
            
        except SyntaxError as e:
            return {
                'valid': False,
                'error': f"语法错误：{e}",
                'line': e.lineno
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }


# 全局沙箱实例
_sandbox = None

def get_sandbox() -> SandboxExecutor:
    """获取全局沙箱实例"""
    global _sandbox
    if _sandbox is None:
        _sandbox = SandboxExecutor()
    return _sandbox


def execute_strategy(code: str, context: dict = None) -> dict:
    """
    便捷函数：执行策略代码
    
    Args:
        code: 策略代码
        context: 执行上下文
    
    Returns:
        dict: 执行结果
    """
    return get_sandbox().execute(code, context)


def validate_strategy(code: str) -> dict:
    """
    便捷函数：验证策略代码
    
    Args:
        code: 策略代码
    
    Returns:
        dict: 验证结果
    """
    return get_sandbox().validate(code)
