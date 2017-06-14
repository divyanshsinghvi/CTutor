#!/bin/bash
python run_cpp_backend.py usercode.c c > test-trace.js
#sed -i '1s/^/var trace= /' test-trace.js
