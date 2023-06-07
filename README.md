# Chrome app development from Windows/Mac/Linux
hendrich@ - June 2023

## Background
Typically, you would develop and build your Chrome app on a Windows/Mac/Linux device. In the past, you were able to run the Chrome app directly on that platform using the local Chrome browser until Chrome apps were deprecated (M104). There used to be a policy-based escape hatch ([ChromeAppsEnabled](https://chromeenterprise.google/intl/en_us/policies/#ChromeAppsEnabled)), which stopped working in M114. The only remaining escape hatch is an allowlist via command line flag (`chrome.exe --enable-features=ChromeAppsDeprecation:allow_list/mplpmdejoamenolpcojgegminhcnmibo`), but that one will also not be around forever (TBD).

This document outlines how you can modify your development flow to continue developing on Windows/Mac/Linux and then testing the built Chrome app on a ChromeOS device with ease. Several engineers at Google have used the same flow for developing Chrome apps/extensions.

## App deployment to ChromeOS
Typically, you would have just launched the local Chrome browser, navigated to the [chrome://extensions](chrome://extensions) page and clicked the “load unpacked” to load the source directory of your app.

In theory, said flow is also possible from the Chromebook. However, this would require you to move the source files to the Chromebook every time (e.g. sync via GoogleDrive) and therefore does not allow quick development cycles.
The alternative would be to upload the source directory to Chrome webstore, but that would take even longer.

Instead, we will
1. pack the Chrome app source directory into a packaged .crx
2. Serve the packaged app from the development machine via self-hosting
3. Force-install it to the Chromebook
4. Refresh the Chromebook to pick up the latest changes

For steps 1+2, I have built an python script that automates these steps for us. That script will be executed whenever you make a change to the sources. Force-installing the extension (step 3) only needs to be set up once. Whenever you want the changes to be reflected on the Chromebook, you can navigate to [chrome://extensions](chrome://extensions) and with a click on “Update”, the Chromebook will automatically pull the latest version of the app from your development machine. The script will automatically increase the app’s minor version in the manifest to trigger an update.
Local extension host script
You can download the script from here. The content’s are:
update_loca_extensiion_host.py - the script you will run to package and serve the updated source directory. 
“host” directory - this is where the packaged .crx and updated update_manifest.xml will land in. This directory will be served from your development machine. You typically don’t have to touch this directory.
“PEMs” directory - this is where the script will organize the private keys used to sign and pack your source directories into a .crx file. The directory also contains an ids.json, which contains the mappings from your source directory names (= identifier) to the used key. You can have the script generate a key for your (resulting in a random extension ID) or use an existing key (resulting in a known extension ID). More on that further below. It is not possible to control the extension ID via “key” attribute in the manifest.json as you would do in the “load unpacked” flow.
Packaging an app

Serving an app



Remote debugging
