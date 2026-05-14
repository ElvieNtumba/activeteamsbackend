# Quick Start - Cell Bounce-Back Fix

## The Problem
Cells captured on Friday appear as "overdue" on Monday. This happens because attendance data was stored with inconsistent date formats (week IDs vs. date strings).

## Quick Fix Summary

### 3 Main Changes:
1. **Better search function** - `find_attendance_for_date()` finds records regardless of date format
2. **Auto-normalization** - After each attendance submission, date keys are normalized
3. **Admin cleanup** - One endpoint to fix all existing data

---

## For Admins: Clean Up Existing Data

### Run cleanup once:
```bash
POST /admin/normalize-event-attendance-keys
```

### What it does:
- Converts all attendance keys to `YYYY-MM-DD` format
- Migrates records from old week format (e.g., `"2025-W50"` → `"2025-12-02"`)
- Shows how many records were fixed

### Result:
After running this, cells will no longer bounce back.

---

## For Developers: Code Changes

### New Functions Added:
- `find_attendance_for_date(attendance_data, target_date)` - Smarter search across date formats
- `normalize_event_attendance_keys(event_id)` - Auto-fix event's attendance keys

### Modified Endpoints:
- `/events/cells` - Uses new search function, auto-normalizes found records
- `/submit-attendance/{event_id}` - Auto-normalizes attendance keys after submission
- `/admin/normalize-event-attendance-keys` - NEW: Bulk cleanup endpoint

### Key Code Lines:
- Line ~195: `find_attendance_for_date()` function
- Line ~240: `normalize_event_attendance_keys()` function  
- Line ~2530: Cell retrieval uses new search
- Line ~7020: Attendance submission calls normalization

---

## Verification

### Before Fix:
```
MongoDB attendance field has mixed keys:
{
  "2025-W50": {...},      ← Week format (old)
  "2026-01-27": {...}     ← Date format (new)
}

Frontend shows event as "incomplete" because it can't find the right record.
```

### After Fix:
```
MongoDB attendance field has consistent keys:
{
  "2025-12-02": {...},    ← All normalized to date format
  "2026-01-27": {...}     ← Consistent format
}

Frontend correctly finds records and shows actual status.
```

---

## Testing

### Manual Test:
1. Capture a cell today
2. Check tomorrow - should show "complete" (not "overdue")
3. Repeat for different days

### Command Line Test:
```bash
# Check attendance records before fix
mongo "your_mongodb"
db.events.findOne({"_id": ObjectId("693932fec89ea1e42b8669cd")}).attendance

# Should show mixed formats like "2025-W50", "2026-01-27"

# After running normalization endpoint
db.events.findOne({"_id": ObjectId("693932fec89ea1e42b8669cd")}).attendance

# Now shows only YYYY-MM-DD format
```

---

## Files Changed
- `main.py` - Core backend changes
- `CELL_BOUNCE_BACK_FIX.md` - Detailed documentation

---

## Support

If cells still bounce back after fix:
1. Check app logs for errors
2. Run the cleanup endpoint again
3. Verify MongoDB connection is working
4. Contact development team with error logs
