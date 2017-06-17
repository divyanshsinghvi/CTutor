#!/bin/bash
var="\\n"
rep="\n"

sed -i 's/\\\\n/\\n/g' new
sed -i 's/\\n/\\\\n/g' new
