// Prints the macOS privacy status Electron (= Catbot's desktop app) has, without prompting.
const { app, systemPreferences } = require("electron");
app.whenReady().then(() => {
  for (const kind of ["microphone", "screen"]) {
    console.log(`${kind.padEnd(10)} ${systemPreferences.getMediaAccessStatus(kind)}`);
  }
  app.quit();
});
