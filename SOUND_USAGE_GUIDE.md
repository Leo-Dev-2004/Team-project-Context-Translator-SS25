# Sound Effects Usage Guide

## Overview
This document describes when and where each sound effect is used in the application.

## Sound Effects Table

| Sound | Status | File Path | Trigger Event | Code Location | User Action |
|-------|--------|-----------|---------------|---------------|-------------|
| 🚀 Launch | ✅ Implemented | `./Sounds/launch_successful.mp3` | WebSocket connection established | `renderer.js` - `_initializeWebSocket()` → `backendWs.onopen` | App connects to backend |
| 🖱️ Click | ✅ Implemented | `./Sounds/click.mp3` | Button clicks | Various UI components | User clicks interactive elements |
| 👋 Join | ✅ Implemented | `./Sounds/join.mp3` | User joins session | `renderer.js` - session join logic | User successfully joins meeting |
| 💡 Explanation | ✅ Implemented | `./Sounds/explanation_received.mp3` | Explanation received | Message handler for explanation messages | App receives term explanation from backend |
| 🔴 Error | ❌ Missing | `./Sounds/error.mp3` | WebSocket error or connection failure | `renderer.js` - `_initializeWebSocket()` → `backendWs.onerror` | Connection fails or error occurs |
| 🔔 Notification | ❌ Missing | `./Sounds/notification.mp3` | General notifications | `_showNotification()` method | Various notification events |
| 🚪 Leave | ❌ Missing | `./Sounds/leave.mp3` | Disconnect or session exit | `renderer.js` - `disconnectedCallback()` and `backendWs.onclose` | User leaves meeting or disconnects |
| 🔇 Mute | ❌ Missing | `./Sounds/mute.mp3` | Microphone muted | Mute button click handler (to be implemented) | User mutes microphone |
| 🔊 Unmute | ❌ Missing | `./Sounds/unmute.mp3` | Microphone unmuted | Unmute button click handler (to be implemented) | User unmutes microphone |

## Detailed Trigger Descriptions

### ✅ Already Implemented

#### 🚀 Launch Sound
**When:** Application establishes WebSocket connection to backend  
**Code:**
```javascript
this.backendWs.onopen = () => {
  console.log('Renderer: ✅ WebSocket connection established.');
  this.updateServerStatus('connected');
  this._performHandshake();
  playSound(launch_sound); // ← Plays here
};
```

#### 🖱️ Click Sound
**When:** User interacts with clickable UI elements  
**Purpose:** Provides immediate tactile feedback for user interactions

#### 👋 Join Sound
**When:** User successfully joins a session  
**Purpose:** Confirms successful session connection

#### 💡 Explanation Sound
**When:** Backend sends an explanation for a term  
**Purpose:** Alerts user that new explanation is available

---

### ❌ To Be Implemented

#### 🔴 Error Sound
**When:** WebSocket connection fails or encounters error  
**Code Location:**
```javascript
this.backendWs.onerror = (error) => {
  this.updateServerStatus('trouble');
  this._showNotification('WebSocket connection failed', 'error');
  playSound(error_sound); // ← Should play here
};
```
**User Experience:** Alerts user to connection problems or errors

#### 🔔 Notification Sound
**When:** General notifications are displayed  
**Code Location:**
```javascript
_showNotificationIfAvailable(message, type) {
  console.log(`Notification (${type}): ${message}`);
  // playSound(notification_sound); // ← Should be added here
}
```
**User Experience:** Draws attention to important messages or updates

#### 🚪 Leave Sound
**When:** User disconnects or leaves session  
**Code Locations:**
```javascript
// Location 1: WebSocket close
this.backendWs.onclose = () => {
  this.updateServerStatus('disconnected');
  console.log('Renderer: ⚙️ WebSocket connection closed.');
  playSound(leave_sound); // ← Already referenced but not implemented
};

// Location 2: Component cleanup
disconnectedCallback() {
  // ... cleanup code ...
  playSound(leave_sound); // ← Already referenced but not implemented
}
```
**User Experience:** Confirms disconnect/departure action

#### 🔇 Mute Sound
**When:** Microphone is muted  
**Implementation Needed:** Mute button click handler  
**Suggested Code:**
```javascript
_handleMuteClick() {
  this.isMuted = true;
  // Update UI
  playSound(mute_sound);
}
```
**User Experience:** Confirms microphone is now muted

#### 🔊 Unmute Sound
**When:** Microphone is unmuted  
**Implementation Needed:** Unmute button click handler  
**Suggested Code:**
```javascript
_handleUnmuteClick() {
  this.isMuted = false;
  // Update UI
  playSound(unmute_sound);
}
```
**User Experience:** Confirms microphone is now active

## Sound Design Considerations

### Volume Balance
All sounds should have similar perceived loudness to avoid jarring transitions. Consider normalizing all sounds to the same peak level.

### Frequency of Use
Some sounds will play more frequently than others:
- **High Frequency:** Click, Mute/Unmute (if users toggle frequently)
- **Medium Frequency:** Notification, Explanation
- **Low Frequency:** Launch, Join, Leave, Error

High-frequency sounds should be more subtle to avoid annoyance.

### Emotional Tone
- **Positive:** Launch (success), Join (welcome), Unmute (enabling)
- **Neutral:** Click (interaction), Notification (information), Explanation (learning)
- **Negative/Alert:** Error (warning), Leave (goodbye), Mute (disabling)

### Duration Guidelines
- **Very Short (0.2-0.5s):** Click, Mute, Unmute
- **Short (0.5-1.0s):** Error, Notification
- **Medium (1.0-1.5s):** Launch, Join, Leave, Explanation

## Testing Checklist

When testing sound implementation:
- [ ] Sound plays at the correct trigger point
- [ ] Volume is appropriate (not too loud or too quiet)
- [ ] Sound completes before the next sound can play (or overlaps gracefully)
- [ ] Sound conveys the intended meaning/emotion
- [ ] Sound is not annoying when heard repeatedly
- [ ] Sound works on different devices/browsers
- [ ] Sound file loads quickly
- [ ] No console errors when sound plays

## Future Enhancements

Consider adding:
- **Volume controls** - Allow users to adjust sound volume or disable sounds
- **Sound themes** - Multiple sound packs for different preferences
- **Accessibility** - Visual indicators as alternatives to sounds
- **Haptic feedback** - Vibration on mobile devices as complement to sounds

---

**Reference:** See `SOUND_FILES_ISSUE.md` for implementation details
