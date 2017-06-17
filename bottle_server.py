# Lightweight OPT server that works on both Python 2 and 3

# NOTE that this is meant only for testing and not deployment, since
# there is no sandboxing

# to invoke, run 'python bottle_server.py'
# and visit http://localhost:8080/index.html
#
# external dependencies: bottle
#
# easy_install pip
# pip install bottle

from bottle import route, get, request, run, template, static_file
try:
    import StringIO # NB: don't use cStringIO since it doesn't support unicode!!!
except:
    import io as StringIO # py3
import json
import pg_logger
#import subprocess 
#from run_cpp_backend import postprocess_stdout
@route('/web_exec_<name:re:.+>.py')
@route('/LIVE_exec_<name:re:.+>.py')
@route('/viz_interaction.py')
@route('/syntax_err_survey.py')
def dummy_ok(name=None):
    return 'OK'

@route('/<filepath:path>')
def index(filepath):
    return static_file(filepath, root='.')


# Note that this will run either Python 2 or 3, depending on which
# version of Python you used to start the server, REGARDLESS of which
# route was taken:
@route('/web_exec_py2.py')
@route('/web_exec_py3.py')
@route('/LIVE_exec_py2.py')
@route('/LIVE_exec_py3.py')
def get_py_exec():
  out_s = StringIO.StringIO()

  def json_finalizer(input_code, output_trace):
    ret = dict(code=input_code, trace=output_trace)
    json_output = json.dumps(ret, indent=None)
    out_s.write(json_output)

  options = json.loads(request.query.options_json)

  pg_logger.exec_script_str_local(request.query.user_script,
                                  request.query.raw_input_json,
                                  options['cumulative_mode'],
                                  options['heap_primitives'],
                                  json_finalizer)

  #return 'OK'
  return out_s.getvalue()
@route('/web_exec_c.py')
def c_exec():
 # Run the Valgrind-based C/C++ backend for OPT and produce JSON to
 # stdout for piping to a web app, properly handling errors and stuff

# Created: 2016-05-09

#import json
 import os
 from subprocess import Popen, PIPE
 import re
 import sys
 
 VALGRIND_MSG_RE = re.compile('==\d+== (.*)$')
 end_of_trace_error_msg = None
 
 DN = os.path.dirname(sys.argv[0])
 if not DN:
     DN = '.' # so that we always have an executable path like ./usercode.exe
 #f = open('usercode.c','r') # string containing the program to be run
 USER_PROGRAM = request.query.user_script#f.read()
 LANG = 'c'#sys.argv[2] # 'c' for C or 'cpp' for C++
 
 prettydump = False
 if len(sys.argv) > 3:
     if sys.argv[3] == '--prettydump':
         prettydump = True
 
 
 if LANG == 'c':
     CC = 'gcc'
     DIALECT = '-std=c11'
     FN = 'usercode.c'
 else:
     CC = 'g++'
     DIALECT = '-std=c++11'
     FN = 'usercode.cpp'
 
 F_PATH = os.path.join(DN, FN)
 VGTRACE_PATH = os.path.join(DN, 'usercode.vgtrace')
 EXE_PATH = os.path.join(DN, 'usercode.exe')
 
 # get rid of stray files so that we don't accidentally use a stray one
 for f in (F_PATH, VGTRACE_PATH, EXE_PATH):
     if os.path.exists(f):
         os.remove(f)
 
 # write USER_PROGRAM into F_PATH
 with open(F_PATH, 'w') as f:
     f.write(USER_PROGRAM)
 
 # compile it!
 p = Popen([CC, DIALECT, '-ggdb', '-O0', '-fno-omit-frame-pointer', '-o', EXE_PATH, F_PATH],
           stdout=PIPE, stderr=PIPE)
 (gcc_stdout, gcc_stderr) = p.communicate()
 gcc_retcode = p.returncode
 
 if gcc_retcode == 0:
     #print >> sys.stderr, '=== gcc stderr ==='
     #print >> sys.stderr, gcc_stderr
     #print >> sys.stderr, '==='
 
     # run it with Valgrind
     VALGRIND_EXE = os.path.join(DN, 'valgrind-3.11.0/inst/bin/valgrind')
     # tricky! --source-filename takes a basename only, not a full pathname:
     valgrind_p = Popen(['stdbuf', '-o0', # VERY IMPORTANT to disable stdout buffering so that stdout is traced properly
                         VALGRIND_EXE,
                         '--tool=memcheck',
                         '--source-filename=' + FN,
                         '--trace-filename=' + VGTRACE_PATH,
                         EXE_PATH],
                        stdout=PIPE, stderr=PIPE)
     (valgrind_stdout, valgrind_stderr) = valgrind_p.communicate()
     valgrind_retcode = valgrind_p.returncode
 
     #print >> sys.stderr, '=== Valgrind stdout ==='
     #print >> sys.stderr, valgrind_stdout
     #print >> sys.stderr, '=== Valgrind stderr ==='
     #print >> sys.stderr, valgrind_stderr
 
     error_lines = []
     in_error_msg = False
     if valgrind_retcode != 0: # there's been an error with Valgrind
         for line in valgrind_stderr.splitlines():
             m = VALGRIND_MSG_RE.match(line)
             if m:
                 msg = m.group(1).rstrip()
                 print >> sys.stderr, msg
                 if 'Process terminating' in msg:
                     in_error_msg = True
 
                 if in_error_msg:
                     if not msg:
                         in_error_msg = False
 
                 if in_error_msg:
                     error_lines.append(msg)
 
         print >> sys.stderr, error_lines
         if error_lines:
             end_of_trace_error_msg = '\n'.join(error_lines)
 
 
     # convert vgtrace into an OPT trace
     print("Yo")
     # TODO: integrate call into THIS SCRIPT since it's simply Python
     # code; no need to call it as an external script
     POSTPROCESS_EXE = os.path.join(DN, 'vg_to_opt_trace.py')
     args = ['python', POSTPROCESS_EXE]
     if prettydump:
         args.append('--prettydump')
     else:
         args.append('--jsondump')
     if end_of_trace_error_msg:
         args += ['--end-of-trace-error-msg', end_of_trace_error_msg]
     args.append(F_PATH)
 
     postprocess_p = Popen(args, stdout=PIPE, stderr=PIPE)
     (postprocess_stdout, postprocess_stderr) = postprocess_p.communicate()
     postprocess_retcode = postprocess_p.returncode
     #print >> sys.stderr, '=== postprocess stderr ==='
     #print >> sys.stderr, postprocess_stderr
     #print >> sys.stderr, '==='
     
     #print postprocess_stdout
 else:
     #print >> sys.stderr, '=== gcc stderr ==='
     #print >> sys.stderr, gcc_stderr
     #print >> sys.stderr, '==='
     # compiler error. parse and report gracefully!
 
     exception_msg = 'unknown compiler error'
     lineno = None
     column = None
 
     # just report the FIRST line where you can detect a line and column
     # number of the error.
     for line in gcc_stderr.splitlines():
         # can be 'fatal error:' or 'error:' or probably other stuff too.
         m = re.search(FN + ':(\d+):(\d+):.+?(error:.*$)', line)
         if m:
             lineno = int(m.group(1))
             column = int(m.group(2))
             exception_msg = m.group(3).strip()
             break
 
         # linker errors are usually 'undefined ' something
         # (this code is VERY brittle)
         if 'undefined ' in line:
             parts = line.split(':')
             exception_msg = parts[-1].strip()
             # match something like
             # /home/pgbovine/opt-cpp-backend/./usercode.c:2: undefined reference to `asdf'
             if FN in parts[0]:
                 try:
                     lineno = int(parts[1])
                 except:
                     pass
             break
 
     ret = {'code': USER_PROGRAM,
            'trace': [{'event': 'uncaught_exception',
                     'exception_msg': exception_msg,
                     'line': lineno}]}
    # print json.dumps(ret)

  #subprocess.call(["python", "/home/dsinghvi/project/CTutor/v5-unity/run_cpp_backend.py"])
 out = StringIO.StringIO()
 out.write(postprocess_stdout)
 #out.write(ret)
 return out.getvalue()

if __name__ == "__main__":
    run(host='localhost', port=8003, reloader=True)
