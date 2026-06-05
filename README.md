# Deal Studio — דוחות כספיים ← אקסל + מצגת

מעלים דוחות (כמה שנים), Claude קורא ומחלץ את המספרים, ומקבלים להורדה את האקסל המלא והמצגת.
**מבנה שטוח:** כל הקבצים באותה רמה — כדי שהעלאה ל-GitHub/שרת לא תתבלבל ממבנה תיקיות.

## הרצה מקומית (מק/לינוקס)
```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
bash run.sh            # ואז פותחים http://localhost:8000
```
Windows: `set ANTHROPIC_API_KEY=...` ואז `run.bat`. בלי מפתח — אפשר להזין ידנית.

## העלאה לאונליין (Render) — גישה עם סיסמה
1. העלה את **כל הקבצים האלה** (לא תיקייה — הקבצים עצמם) למאגר GitHub פרטי, ברמה העליונה.
2. ב-render.com: New → Blueprint → בחר את המאגר (יזהה את `render.yaml`).
3. הזן סודות: `ANTHROPIC_API_KEY` ו-`APP_PASSWORD` (סיסמת הגישה ללקוחות).
4. כשהסטטוס Live — תקבל כתובת `https://…onrender.com`. שתף אותה + הסיסמה.

הכניסה (מסך סיסמה) מופעלת אוטומטית כש-`APP_PASSWORD` מוגדר. מקומית בלי המשתנה — פתוח.

## משתני סביבה
`ANTHROPIC_API_KEY` (חובה לחילוץ) · `APP_PASSWORD` (כניסה) · `SESSION_SECRET` (נוצר ע"י Render) ·
`COOKIE_SECURE=1` (בפרודקשן) · `MAX_EXTRACTS_PER_HOUR` (ברירת מחדל 60) · `ANTHROPIC_MODEL` (ברירת מחדל claude-sonnet-4-6).

## הקבצים (כולם באותה רמה)
app.py · schema.py · populate_deck.py · build_workbook.py · deck_template.html ·
index.html · requirements.txt · Dockerfile · render.yaml · run.sh · run.bat
