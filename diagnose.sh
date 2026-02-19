#!/bin/bash
echo "--- DF ---" > diagnose.log
df -h . >> diagnose.log
echo "--- LS ---" >> diagnose.log
ls -l >> diagnose.log
echo "--- PS ---" >> diagnose.log
ps aux | grep "app.py" | grep -v grep >> diagnose.log
echo "--- LOGS ---" >> diagnose.log
tail -n 20 server.log >> diagnose.log
