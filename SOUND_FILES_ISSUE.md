# Sound Files Implementation Issue

## Overview
The application currently has several sound files marked as "NOT IMPLEMENTED YET" in `Frontend/src/renderer.js`. These sound effects need to be sourced, added to the project, and properly integrated.

## Current Status

### ✅ Already Implemented
- `launch_sound` → `./Sounds/launch_successful.mp3` - Plays when app launches/connects
- `click_sound` → `./Sounds/click.mp3` - Plays on button clicks
- `join_sound` → `./Sounds/join.mp3` - Plays when joining a session
- `explanation_sound` → `./Sounds/explanation_received.mp3` - Plays when explanation is received

### ❌ Missing Sound Files
The following sound variables are currently set to `'NOT IMPLEMENTED YET'`:

1. **error_sound** - Should play when errors occur (WebSocket failures, etc.)
2. **notification_sound** - Should play for general notifications
3. **leave_sound** - Should play when leaving/disconnecting from a session
4. **mute_sound** - Should play when microphone is muted
5. **unmute_sound** - Should play when microphone is unmuted

## Sound Source
All sounds should be sourced from: **[Modern User Interface Sound Effects](https://creatorassets.com/a/modern-user-interface-sound-effects)**

This library provides royalty-free UI sound effects that are perfect for our application.

## Team Assignments

### Task 1: Error Sound 🔴
**Assigned to:** _[Team Member Name]_

**Requirements:**
- Find an appropriate error/alert sound from the sound library
- Sound should be clear but not too harsh
- Duration: 0.3-1.0 seconds recommended
- Suggested keywords: "error", "alert", "warning", "fail"

**Recommended sounds:**
- Alert/Error notification sounds
- Short buzzer or beep sounds
- Negative feedback sounds

**File path:** `Frontend/Sounds/error.mp3`

---

### Task 2: Notification Sound 🔔
**Assigned to:** _[Team Member Name]_

**Requirements:**
- Find a pleasant, non-intrusive notification sound
- Sound should be attention-grabbing but not annoying
- Duration: 0.5-1.5 seconds recommended
- Suggested keywords: "notification", "ding", "chime", "message"

**Recommended sounds:**
- Light bell or chime sounds
- Soft notification pings
- Gentle alert tones

**File path:** `Frontend/Sounds/notification.mp3`

---

### Task 3: Leave Sound 🚪
**Assigned to:** _[Team Member Name]_

**Requirements:**
- Find a sound that indicates disconnection/departure
- Should be distinct from the join sound
- Duration: 0.5-1.5 seconds recommended
- Suggested keywords: "disconnect", "exit", "close", "whoosh down"

**Recommended sounds:**
- Descending tones
- Door close sounds
- Disconnect/shutdown sounds
- Fade-out whoosh effects

**File path:** `Frontend/Sounds/leave.mp3`

---

### Task 4: Mute Sound 🔇
**Assigned to:** _[Team Member Name]_

**Requirements:**
- Find a sound that clearly indicates audio is being muted
- Should be short and definitive
- Duration: 0.2-0.8 seconds recommended
- Suggested keywords: "mute", "off", "click down", "disable"

**Recommended sounds:**
- Short click or toggle sounds
- Soft thud or close sound
- Descending pitch sounds

**File path:** `Frontend/Sounds/mute.mp3`

---

### Task 5: Unmute Sound 🔊
**Assigned to:** _[Team Member Name]_

**Requirements:**
- Find a sound that clearly indicates audio is being enabled
- Should pair well with the mute sound (consider opposite/complementary sound)
- Duration: 0.2-0.8 seconds recommended
- Suggested keywords: "unmute", "on", "click up", "enable"

**Recommended sounds:**
- Short click or toggle sounds
- Soft open sound
- Ascending pitch sounds (opposite of mute sound)

**File path:** `Frontend/Sounds/unmute.mp3`

---

## Technical Specifications

### File Requirements
- **Format:** MP3 (preferred) or WAV
- **Sample Rate:** 44.1kHz or 48kHz
- **Bit Rate:** 128-320 kbps for MP3
- **Channels:** Mono or Stereo (Mono preferred for smaller file size)
- **File Size:** Keep under 100KB per file when possible

### Directory Structure
```
Frontend/
  └── Sounds/
      ├── launch_successful.mp3  ✅ (exists)
      ├── click.mp3              ✅ (exists)
      ├── join.mp3               ✅ (exists)
      ├── explanation_received.mp3 ✅ (exists)
      ├── error.mp3              ❌ (to be added)
      ├── notification.mp3       ❌ (to be added)
      ├── leave.mp3              ❌ (to be added)
      ├── mute.mp3               ❌ (to be added)
      └── unmute.mp3             ❌ (to be added)
```

### Naming Convention
- Use lowercase with underscores for multi-word names
- Use `.mp3` extension
- Be descriptive but concise

## Implementation Steps

For each sound file, the assigned team member should:

1. **Browse the Sound Library**
   - Visit https://creatorassets.com/a/modern-user-interface-sound-effects
   - Preview sounds that match the requirements
   - Select the most appropriate sound

2. **Download and Prepare**
   - Download the selected sound file
   - Ensure it meets technical specifications
   - Convert format if necessary (use tools like Audacity, FFmpeg, or online converters)
   - Optimize file size if needed

3. **Add to Repository**
   - Place the file in `Frontend/Sounds/` directory
   - Use the exact filename specified in the task
   - Verify the file plays correctly

4. **Update Code**
   - Update `Frontend/src/renderer.js`
   - Replace `'NOT IMPLEMENTED YET'` with the correct path
   - Example: `const error_sound = './Sounds/error.mp3';`

5. **Test**
   - Test the sound in the application
   - Verify volume levels are appropriate
   - Ensure the sound plays at the right trigger points

## Code Changes Required

In `Frontend/src/renderer.js`, update these lines:

```javascript
// Before:
const error_sound = 'NOT IMPLEMENTED YET';
const notification_sound = 'NOT IMPLEMENTED YET';
const leave_sound = 'NOT IMPLEMENTED YET';
const mute_sound = 'NOT IMPLEMENTED YET';
const unmute_sound = 'NOT IMPLEMENTED YET';

// After:
const error_sound = './Sounds/error.mp3';
const notification_sound = './Sounds/notification.mp3';
const leave_sound = './Sounds/leave.mp3';
const mute_sound = './Sounds/mute.mp3';
const unmute_sound = './Sounds/unmute.mp3';
```

## Where Sounds Are Used

Reference the following locations in the codebase where these sounds are triggered:

- **error_sound**: Triggered in `_initializeWebSocket()` when `this.backendWs.onerror` occurs
- **notification_sound**: Used in `_showNotification()` for general notifications
- **leave_sound**: Triggered in `disconnectedCallback()` and `this.backendWs.onclose()`
- **mute_sound**: Would be triggered when mute button is clicked (implementation needed)
- **unmute_sound**: Would be triggered when unmute button is clicked (implementation needed)

## Quality Guidelines

When selecting sounds, consider:

1. **Consistency**: All sounds should feel like they belong to the same UI family
2. **Volume**: Ensure similar volume levels across all sounds (normalize if needed)
3. **Duration**: Keep sounds brief to avoid disrupting user experience
4. **Clarity**: Sounds should be clear and serve their intended purpose
5. **Pleasantness**: Avoid harsh or annoying sounds that users might find irritating
6. **Accessibility**: Consider that these sounds will be heard frequently

## Checklist for Each Team Member

- [ ] Access the sound library at creatorassets.com
- [ ] Preview and select appropriate sound
- [ ] Download the sound file
- [ ] Verify/convert to MP3 format if needed
- [ ] Optimize file size (target <100KB)
- [ ] Add file to `Frontend/Sounds/` directory with correct name
- [ ] Update `Frontend/src/renderer.js` with correct path
- [ ] Test the sound in the application
- [ ] Verify volume and quality
- [ ] Create a pull request with your changes
- [ ] Note in PR description which sound from the library you selected

## Questions or Issues?

If you encounter any problems or have questions about:
- Sound selection criteria
- Technical specifications
- File format conversion
- Integration testing

Please reach out to the team lead or post in the project channel.

## License and Attribution

Ensure all selected sounds from the Modern User Interface Sound Effects library are properly licensed for use in this project. Check the license terms on creatorassets.com and add any required attribution to the project documentation if necessary.

---

**Last Updated:** 2025-10-09  
**Issue Created For:** PR #103
