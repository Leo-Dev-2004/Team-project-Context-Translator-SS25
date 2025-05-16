// src/meet.js
import { meet } from '@googleworkspace/meet-addons/meet.addons';

const CLOUD_PROJECT_NUMBER = '123456789012';   // aus der Google-Cloud-Konsole
export async function initMeet() {
  const session = await meet.addon.createAddonSession({ cloudProjectNumber: CLOUD_PROJECT_NUMBER });
  return await session.createSidePanelClient();
}
