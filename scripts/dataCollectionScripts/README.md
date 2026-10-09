# Data Collection – Master Script

Runs the cellular data collection across all connected phones and saves the logs (including QMDL) to an external hard drive.

---

## Usage

```bash
./scripts/dataCollectionScripts/masterScript.sh <num_runs> <location>
```

**Example**

```bash
./scripts/dataCollectionScripts/masterScript.sh 4 bharti501
```

| Argument     | Meaning                        | Example     |
|--------------|--------------------------------|-------------|
| `num_runs`   | Number of runs to perform      | `4`         |
| `location`   | Name of the test location      | `bharti501` |

> **Important:** Run the command from **outside** the `scripts` folder (i.e., from the repository root), exactly as shown above.

---

## Before Running the Test (Pre-Flight Checks)

### 1. Check that all three phones are connected

```bash
adb devices
```

All **three** devices should be listed with the status `device`.

If any device is missing (or shows `unauthorized` / `offline`):
1. Restart the phone.
2. Unplug and plug it back in.
3. Run `adb devices` again until all three are listed.

### 2. Plug in the external hard drive

Make sure the hard drive is connected and mounted before starting.

- **macOS users:** No changes needed. The script uses `/Volumes/...` by default.
- **Linux / Windows users:** Open `scripts/dataCollectionScripts/masterScript.sh` and update the `DATA_DIR` variable. Replace `Volumes` with the correct mount path of your hard drive.

---

## After the First Run (Post-checks)

Once **one run** has completed, verify that **QMDL data has been collected for every operator** by checking the hard drive at:

```
data/<operator>/<location>/<date>/run
```

| Placeholder  | Meaning                                   |
|--------------|-------------------------------------------|
| `<operator>` | Operator name (one folder per operator)   |
| `<location>` | Location passed to the script, e.g. `bharti501` |
| `<date>`     | Date of the test                          |

If QMDL files are missing for any operator, stop the test, check that device's connection (`adb devices`), and restart the collection.

---

## Quick Checklist

- [ ] Running from outside the `scripts` folder
- [ ] `adb devices` shows all three phones
- [ ] Hard drive plugged in
- [ ] `DATA_DIR` updated (non-Mac users only)
- [ ] After run 1: QMDL present for all operators on the hard drive