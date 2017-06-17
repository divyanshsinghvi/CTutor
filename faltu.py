from subprocess import call
try:
    import StringIO
except:
    import io as StringIO
from run_cpp_backend import postprocess_stdout
out = StringIO.StringIO()
print(postprocess_stdout)
