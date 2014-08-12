#!/bin/bash

CLASSPATH="" # clear the classpath. Everything is provided

for f in lib/*.jar; do
    CLASSPATH=$CLASSPATH:$f:resources
done

CLASSPATH=$CLASSPATH:src;
echo $CLASSPATH

if [ $# -eq 0 ]; then
     java -Xmx1024m -cp $CLASSPATH clojure.main
else
     java -Xmx1024m -cp $CLASSPATH clojure.main $1 — $@
fi
