@echo off
cd /d "D:\Projects\Claude Projects\Household Expense Tracker\Household Expense Tracker Build"
git add -A
git commit -m "v2.4: Remove purple entries card, custom pill-chip legend for donut chart"
git push origin main > push_log.txt 2>&1
echo --- >> push_log.txt
git log --oneline -3 >> push_log.txt 2>&1
