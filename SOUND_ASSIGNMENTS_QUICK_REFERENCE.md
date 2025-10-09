# Sound Files - Quick Assignment Reference

## 🎵 Missing Sound Files for Implementation

Visit sound library: **https://creatorassets.com/a/modern-user-interface-sound-effects**

---

## 📋 Team Assignments

| Sound Type | Team Member | File Name | Keywords to Search | Status |
|------------|-------------|-----------|-------------------|--------|
| 🔴 Error | _[Assign Name]_ | `error.mp3` | "error", "alert", "warning", "fail" | ⬜ Todo |
| 🔔 Notification | _[Assign Name]_ | `notification.mp3` | "notification", "ding", "chime" | ⬜ Todo |
| 🚪 Leave | _[Assign Name]_ | `leave.mp3` | "disconnect", "exit", "whoosh down" | ⬜ Todo |
| 🔇 Mute | _[Assign Name]_ | `mute.mp3` | "mute", "off", "click down" | ⬜ Todo |
| 🔊 Unmute | _[Assign Name]_ | `unmute.mp3` | "unmute", "on", "click up" | ⬜ Todo |

---

## ✅ Quick Steps

1. Go to https://creatorassets.com/a/modern-user-interface-sound-effects
2. Search for your sound using the keywords
3. Download as MP3
4. Place in `Frontend/Sounds/` with the filename above
5. Update `Frontend/src/renderer.js`:
   ```javascript
   const your_sound = './Sounds/your_filename.mp3';
   ```
6. Test and create PR

---

## 📁 File Location
All files go in: `Frontend/Sounds/`

## 📝 Code Update Location
Update in: `Frontend/src/renderer.js` (lines 13-17)

## 🎯 Target Specs
- Format: MP3
- Size: < 100KB
- Duration: 0.3-1.5 seconds
- Quality: 128-320 kbps

---

For detailed instructions, see **SOUND_FILES_ISSUE.md**
