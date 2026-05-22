# Cell Event Bounce-Back Issue - Fix Documentation

## Problem Summary
Recurring cell events were being captured successfully but then **reappeared as "overdue" or "not captured" the next day** (commonly between Wednesday-Friday). This created a "bounce-back" effect where:
1. User captures a cell on Friday → Status shows "complete" ✓
2. Next morning (Saturday/Monday) → Status shows "incomplete/overdue" ✗

## Root Cause Analysis
The issue was caused by **inconsistent date key formats** in the `attendance` field of MongoDB documents:

### Data Format Inconsistency
The same event's attendance data used **multiple date formats**:
- **Week identifiers**: `"2025-W50"`, `"2025-W51"` (ISO 8601 week format)
- **Exact dates**: `"2026-01-27"`, `"2026-02-03"` (ISO 8601 date format)

### The Flow That Caused The Bug
1. **Attendance submission** stored records with keys like `"2026-01-27"`
2. **Cell retrieval logic** in `/events/cells` looked for exact date matches
3. **When looking for past records**, the code searched for `"2026-01-20"` but found nothing because:
   - Old data was keyed as `"2025-W50"` (week format)
   - Migration logic failed silently
   - System defaulted to "incomplete" status
4. **Result**: Previously captured cells showed as uncaptured/overdue

### Why It Happened Mostly Wed-Fri
- **Timing of retrieval**: Frontend fetches 4 weeks of past data for "incomplete" status (line 2394)
- **Leap week calculation**: When calculating past Tuesdays across weeks with different date formats, the mismatch became apparent
- **Accumulation**: Multiple attendance records stored in different formats increased the failure rate

## Solution Implemented

### 1. **New Helper Function: `find_attendance_for_date()`**
- Searches across multiple date format variations
- **Order of search**:
  1. Exact ISO date (`"2026-01-20"`)
  2. ISO week format (`"2026-W04"`)
  3. Search through all keys for `event_date_exact` matches
  4. Search through all keys for `event_date_iso` matches
- **Location**: [main.py line ~200](main.py#L200)

### 2. **Normalization Function: `normalize_event_attendance_keys()`**
- Converts non-canonical keys to standard `YYYY-MM-DD` format
- Runs automatically after every attendance submission
- Idempotent—safe to run multiple times
- **Location**: [main.py line ~240](main.py#L240)

### 3. **Updated Attendance Submission**
- After recording attendance, automatically normalizes that event's keys
- Prevents new mismatches from forming
- **Location**: [main.py line ~7020](main.py#L7020)

### 4. **Improved Cell Retrieval Logic**
- Uses `find_attendance_for_date()` instead of simple dictionary lookup
- Automatically migrates found records to canonical format
- Prevents recurrence of the issue
- **Location**: [main.py line ~2450](main.py#L2450)

### 5. **Admin Maintenance Endpoint**
- **POST** `/admin/normalize-event-attendance-keys`
- Normalizes ALL events' attendance records at once
- Shows migration statistics
- **Required role**: `admin`
- **Usage**: One-time cleanup for existing data

## How to Fix Existing Data

### Step 1: Backup Your Database
```bash
# MongoDB backup command (optional but recommended)
mongodump --uri "your-mongodb-uri"
```

### Step 2: Run the Normalization Endpoint
Make a POST request with admin credentials:
```bash
curl -X POST http://localhost:8000/admin/normalize-event-attendance-keys \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

Or from your frontend/admin panel (if available):
```javascript
// Using fetch
fetch('/admin/normalize-event-attendance-keys', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_ADMIN_TOKEN'
  }
})
.then(res => res.json())
.then(data => console.log(data))
```

### Step 3: Monitor Progress
The endpoint logs:
- Number of events processed
- Number of records migrated
- Any errors encountered

Example output:
```
================================================================================
STARTING ATTENDANCE KEY NORMALIZATION FOR ALL EVENTS
================================================================================

Found 245 events with attendance data

[1/245] Blessing Mbele - Die Fakkel High School - Tuesday
   ✓ Migrated 8 attendance records to canonical format

[2/245] Church Prayer Meeting - Wednesday
   ✓ Migrated 5 attendance records to canonical format

...

================================================================================
NORMALIZATION COMPLETE
Events processed: 245
Events normalized: 87
Total records migrated: 342
================================================================================
```

## Technical Details

### Canonical Date Format: `YYYY-MM-DD`
- ISO 8601 standard
- Examples: `"2026-01-20"`, `"2026-05-12"`
- **Why**: Consistent, sortable, timezone-neutral at the date level

### Migration Safety
- **Non-destructive**: Only adds canonical keys; old keys removed after confirmation
- **Idempotent**: Can be run multiple times safely
- **Async**: Each event updates independently

### Backward Compatibility
- Old week-format keys still searchable during transition
- Automatic migration on first attendance submission
- No API changes required

## Verification

### Before Fix
```javascript
// MongoDB query
db.events.findOne({"_id": ObjectId("693932fec89ea1e42b8669cd")})

// Result - Mixed formats
{
  attendance: {
    "2025-W50": {...},      // Week format
    "2025-W51": {...},      // Week format
    "2026-01-27": {...},    // Date format
    "2026-02-03": {...}     // Date format
  }
}
```

### After Fix
```javascript
// All keys in canonical date format
{
  attendance: {
    "2025-12-02": {...},    // Normalized
    "2025-12-09": {...},    // Normalized
    "2026-01-27": {...},    // Already correct
    "2026-02-03": {...}     // Already correct
  }
}
```

## Expected Outcomes

After applying this fix:
1. ✓ Cells captured on Friday will remain "complete" on Monday
2. ✓ No more "bounce-back" or showing as overdue after capture
3. ✓ Consistent retrieval across week boundaries
4. ✓ Better performance (faster lookups with canonical keys)
5. ✓ Future-proof (new submissions use normalized format)

## Files Modified

- `main.py`:
  - Added `find_attendance_for_date()` function
  - Added `normalize_event_attendance_keys()` function
  - Updated `/submit-attendance/{event_id}` endpoint
  - Updated `/events/cells` endpoint
  - Added `/admin/normalize-event-attendance-keys` endpoint

## Testing Recommendations

### Manual Test
1. Have an admin account ready
2. Capture a cell event today
3. Check that it shows as "complete"
4. Check again tomorrow—should still be "complete"
5. Repeat for different days of the week

### Running Normalization
1. Note your current event count: `db.events.countDocuments()`
2. Run the normalization endpoint
3. Verify result shows migrations
4. Spot-check MongoDB records for canonical format

### Monitoring
Monitor the application logs for errors during:
- Attendance submission
- Cell retrieval
- Normalization process

## Rollback (If Needed)

If issues arise after normalization:
1. Restore MongoDB backup: `mongorestore --uri "your-mongodb-uri"`
2. Restart the application
3. Report the issue with error logs

---

**For questions or issues, check application logs with debug filter:**
```bash
# Docker logs
docker logs -f container_name | grep -i "attendance\|normalize"

# Python logs
grep -i "attendance\|normalize" your_app.log
```
