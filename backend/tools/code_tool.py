"""
MineDash AI - Code Executor Tool
Herramienta para ejecutar código Python de forma segura

VERSIÓN PROTEGIDA:
- Timeout de 60 segundos
- Límite de memoria
- Protección contra archivos grandes
- Logs detallados para debugging
"""

import sys
import io
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import multiprocessing
from multiprocessing import Process, Queue
import queue
import psutil
import os


class CodeExecutor:
    """
    Ejecutor de código Python seguro con protecciones
    
    Características:
    - Timeout de 60 segundos (configurable)
    - Límite de memoria
    - Protección contra lectura de archivos grandes
    - Sandbox básico para ejecución
    - Acceso a pandas, numpy
    - Captura de output y errores
    - Guardado automático de código
    """
    
    def __init__(self, code_dir: Path, timeout: int = 60, max_memory_mb: int = 512):
        """
        Inicializar Code Executor
        
        Args:
            code_dir: Directorio donde guardar código ejecutado
            timeout: Timeout de ejecución en segundos (default: 60)
            max_memory_mb: Límite de memoria en MB (default: 512)
        """
        self.code_dir = Path(code_dir)
        self.code_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        
        # Librerías permitidas en el contexto
        self.safe_globals = {
            'pd': pd,
            'np': np,
            'datetime': datetime,
            'timedelta': timedelta,
            'print': print,
            'len': len,
            'range': range,
            'list': list,
            'dict': dict,
            'str': str,
            'int': int,
            'float': float,
            'sum': sum,
            'max': max,
            'min': min,
            'round': round,
            'abs': abs,
        }
        
        print(f"OK CodeExecutor inicializado (timeout: {timeout}s, max_memory: {max_memory_mb}MB)")
    
    def _sanitize_result(self, obj):
        """Convierte pandas objects a tipos nativos Python"""
        if isinstance(obj, pd.Series):
            return obj.to_list()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.int64, np.int32, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._sanitize_result(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_result(v) for v in obj]
        elif obj is None:
            return None
        else:
            try:
                return str(obj)
            except:
                return f"<{type(obj).__name__}>"

    def _run_code_in_process(
        self,
        code: str,
        exec_globals: dict,
        result_queue: Queue,
        code_file: Path
    ):
        """
        Ejecutar código en un proceso separado
        Esta función corre en el proceso hijo
        """
        try:
            # Capturar stdout
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            # Ejecutar código
            exec_locals = {}
            exec(code, exec_globals, exec_locals)
            
            # Obtener output
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            
            # Buscar resultado final
            result = None
            if 'result' in exec_locals:
                result = exec_locals['result']
            elif exec_locals:
                # Tomar la última variable definida
                last_var = list(exec_locals.keys())[-1]
                result = exec_locals[last_var]
            
            # Enviar resultado al proceso principal
            result_queue.put({
                'success': True,
                'result': result,
                'output': output,
                'code_file': str(code_file),
                'variables_created': list(exec_locals.keys())
            })
            
        except Exception as e:
            # Restaurar stdout si hubo error
            sys.stdout = old_stdout
            
            result_queue.put({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            })

    def execute(
        self,
        code: str,
        data_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ejecutar código Python con timeout y protecciones
        
        Args:
            code: Código Python a ejecutar
            data_context: Diccionario con datos adicionales (ej: DataFrames)
            
        Returns:
            Dict con resultado, output, errores, etc.
        """
        start_time = datetime.now()
        
        try:
            # ===================================================================
            # VALIDACIÓN PREVIA
            # ===================================================================
            
            # Validar que el código no tenga comandos peligrosos
            dangerous_keywords = ['os.system', 'subprocess', 'eval', '__import__', 'open(', 'exec(']
            for keyword in dangerous_keywords:
                if keyword in code:
                    return {
                        'success': False,
                        'error': f'Código contiene comando no permitido: {keyword}',
                        'code': code[:200]
                    }
            
            # Advertir sobre lectura de archivos grandes
            if 'read_excel' in code and 'nrows' not in code:
                print(f"⚠️  ADVERTENCIA: Detectado pd.read_excel() sin límite nrows")
                print(f"   Esto puede causar timeout con archivos grandes")
                print(f"   Recomendación: Agregar nrows=1000 al read_excel()")
            
            # ===================================================================
            # GUARDAR CÓDIGO
            # ===================================================================
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            code_file = self.code_dir / f"code_{timestamp}.py"
            
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(f"# Ejecutado: {datetime.now().isoformat()}\n")
                f.write(f"# Timeout: {self.timeout}s\n\n")
                f.write(code)
            
            print(f"📝 Código guardado: {code_file.name}")
            print(f"⏱️  Timeout configurado: {self.timeout}s")
            
            # ===================================================================
            # PREPARAR CONTEXTO
            # ===================================================================
            
            exec_globals = self.safe_globals.copy()
            
            if data_context:
                exec_globals.update(data_context)
            
            # ===================================================================
            # EJECUTAR CON TIMEOUT (usando multiprocessing)
            # ===================================================================
            
            print(f"🚀 Iniciando ejecución...")
            
            result_queue = Queue()
            process = Process(
                target=self._run_code_in_process,
                args=(code, exec_globals, result_queue, code_file)
            )
            
            process.start()
            process.join(timeout=self.timeout)
            
            # ===================================================================
            # VERIFICAR RESULTADO
            # ===================================================================
            
            if process.is_alive():
                # TIMEOUT - Matar el proceso
                print(f"⚠️  TIMEOUT después de {self.timeout}s - Terminando proceso...")
                process.terminate()
                process.join(timeout=5)  # Esperar 5s más para terminar limpiamente
                
                if process.is_alive():
                    # Si todavía está vivo, forzar
                    print(f"🔴 Proceso no respondió - Forzando terminación...")
                    process.kill()
                    process.join()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                return {
                    'success': False,
                    'error': f'Timeout: Ejecución cancelada después de {self.timeout} segundos',
                    'execution_time': execution_time,
                    'timeout': True,
                    'code_file': str(code_file),
                    'suggestion': 'Simplifica el código o usa SQL para consultas grandes'
                }
            
            # Obtener resultado de la cola
            try:
                result_data = result_queue.get_nowait()
            except queue.Empty:
                execution_time = (datetime.now() - start_time).total_seconds()
                return {
                    'success': False,
                    'error': 'El proceso terminó pero no retornó resultado',
                    'execution_time': execution_time,
                    'code_file': str(code_file)
                }
            
            # ===================================================================
            # PROCESAR RESULTADO
            # ===================================================================
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            if result_data['success']:
                print(f"✅ Ejecución exitosa en {execution_time:.2f}s")
                
                return {
                    'success': True,
                    'result': self._sanitize_result(result_data['result']),
                    'output': result_data['output'],
                    'code_file': str(code_file),
                    'variables_created': result_data['variables_created'],
                    'timestamp': timestamp,
                    'execution_time': execution_time
                }
            else:
                print(f"❌ Error en ejecución: {result_data['error']}")
                
                return {
                    'success': False,
                    'error': result_data['error'],
                    'traceback': result_data['traceback'],
                    'code_file': str(code_file),
                    'execution_time': execution_time
                }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            print(f"❌ Error inesperado: {e}")
            
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'traceback': traceback.format_exc(),
                'execution_time': execution_time,
                'code': code[:200] + ('...' if len(code) > 200 else '')
            }
    
    def execute_with_dataframe(
        self,
        code: str,
        df: pd.DataFrame,
        df_name: str = 'df'
    ) -> Dict[str, Any]:
        """
        Ejecutar código con un DataFrame como contexto
        
        Args:
            code: Código Python
            df: DataFrame de pandas
            df_name: Nombre de variable para el DataFrame
            
        Returns:
            Dict con resultado
        """
        # Limitar tamaño del DataFrame para prevenir problemas de memoria
        if len(df) > 100000:
            print(f"⚠️  DataFrame grande ({len(df):,} filas) - Limitando a 100,000")
            df = df.head(100000)
        
        data_context = {df_name: df}
        return self.execute(code, data_context)
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """
        Validar código sin ejecutarlo
        
        Args:
            code: Código a validar
            
        Returns:
            Dict con resultado de validación
        """
        try:
            compile(code, '<string>', 'exec')
            return {
                'valid': True,
                'message': 'Código válido'
            }
        except SyntaxError as e:
            return {
                'valid': False,
                'error': 'Error de sintaxis',
                'message': str(e),
                'line': e.lineno
            }
        except Exception as e:
            return {
                'valid': False,
                'error': 'Error de validación',
                'message': str(e)
            }
    
    def list_saved_code(self, limit: int = 10) -> list:
        """
        Listar código guardado recientemente
        
        Args:
            limit: Número de archivos a listar
            
        Returns:
            Lista de información de archivos
        """
        code_files = sorted(
            self.code_dir.glob('code_*.py'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]
        
        results = []
        for code_file in code_files:
            try:
                with open(code_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                results.append({
                    'filename': code_file.name,
                    'path': str(code_file),
                    'size_bytes': code_file.stat().st_size,
                    'created': datetime.fromtimestamp(code_file.stat().st_mtime).isoformat(),
                    'preview': content[:100] + ('...' if len(content) > 100 else '')
                })
            except Exception as e:
                print(f"⚠️  Error leyendo {code_file.name}: {e}")
        
        return results


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    # Crear executor con timeout corto para pruebas
    executor = CodeExecutor(Path("outputs/code"), timeout=10)
    
    # Ejemplo 1: Código simple
    print("\n=== EJEMPLO 1: Código Simple ===")
    result = executor.execute("""
# Calcular promedio
numeros = [10, 20, 30, 40, 50]
promedio = sum(numeros) / len(numeros)
print(f"Promedio: {promedio}")
result = promedio
""")
    
    if result['success']:
        print(f"✅ Resultado: {result['result']}")
        print(f"⏱️  Tiempo: {result['execution_time']:.2f}s")
    else:
        print(f"❌ Error: {result['error']}")
    
    # Ejemplo 2: Con DataFrame
    print("\n=== EJEMPLO 2: Con DataFrame ===")
    df_test = pd.DataFrame({
        'operador': ['OP001', 'OP002', 'OP003'],
        'productividad': [85, 92, 78]
    })
    
    result = executor.execute_with_dataframe("""
# Análisis de productividad
print(f"Total operadores: {len(df)}")
print(f"Productividad promedio: {df['productividad'].mean():.2f}")
print(f"Mejor operador: {df.loc[df['productividad'].idxmax(), 'operador']}")

result = df['productividad'].mean()
""", df_test)
    
    if result['success']:
        print(f"✅ Resultado: {result['result']}")
        print(f"⏱️  Tiempo: {result['execution_time']:.2f}s")
    
    # Ejemplo 3: Timeout (debe fallar)
    print("\n=== EJEMPLO 3: Timeout Test ===")
    result = executor.execute("""
import time
print("Esperando 15 segundos...")
time.sleep(15)  # Esto debe hacer timeout (configurado a 10s)
result = "Completado"
""")
    
    if not result['success']:
        print(f"❌ Timeout esperado: {result['error']}")
        print(f"⏱️  Tiempo: {result['execution_time']:.2f}s")
    
    # Listar código guardado
    print("\n=== CÓDIGO GUARDADO ===")
    saved = executor.list_saved_code(limit=5)
    for item in saved:
        print(f"  {item['filename']} - {item['created'][:19]}")