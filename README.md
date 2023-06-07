# ChromeOS extension/app development from Windows/Mac/Linux
hendrich@ - June 2023

## Background
Typically, you would develop and build your Chrome app on a Windows/Mac/Linux device. In the past, you were able to run the Chrome app directly on that platform using the local Chrome browser until Chrome apps were deprecated (M104). There used to be a policy-based escape hatch ([ChromeAppsEnabled](https://chromeenterprise.google/intl/en_us/policies/#ChromeAppsEnabled)), which stopped working in M114. The only remaining escape hatch is an allowlist via command line flag (`chrome.exe --enable-features=ChromeAppsDeprecation:allow_list/mplpmdejoamenolpcojgegminhcnmibo`), but that one will also not be around forever (TBD).

This document outlines how you can modify your development flow to continue developing on Windows/Mac/Linux and then testing the built Chrome app on a ChromeOS device with ease. Several engineers at Google have used the same flow for developing Chrome apps/extensions.

## App deployment to ChromeOS
Typically, you would have just launched the local Chrome browser, navigated to the [chrome://extensions](chrome://extensions) page and clicked the `Load unpacked` to load the source directory of your app.

In theory, said flow is also possible from the Chromebook. However, this would require you to move the source files to the Chromebook every time (e.g. sync via GoogleDrive) and therefore does not allow quick development cycles.
The alternative would be to upload the source directory to Chrome webstore, but that would take even longer.

Instead, we will
1. pack the Chrome app source directory into a packaged `.crx`
2. Serve the packaged app from the development machine via self-hosting
3. Force-install it to the Chromebook
4. Refresh the Chromebook to pick up the latest changes

For steps 1+2, I have built an python script that automates these steps for us. That script will be executed whenever you make a change to the sources. Force-installing the extension (step 3) only needs to be set up once. Whenever you want the changes to be reflected on the Chromebook, you can navigate to [chrome://extensions](chrome://extensions) and with a click on `Update`, the Chromebook will automatically pull the latest version of the app from your development machine. The script will automatically increase the app’s minor version in the manifest to trigger an update.

### Contents
* `update_local_extension_host.py` - the script you will run to package and serve the updated source directory. 
* `host` directory - this is where the packaged `.crx` and updated `update_manifest.xml` will land in. This directory will be served from your development machine. You typically don’t have to touch this directory.
* `PEMs` directory - this is where the script will organize the private keys used to sign and pack your source directories into a `.crx` file. The directory also contains an `ids.json`file, which contains the mappings from your source directory names (= app identifier) to the used key. You can have the script generate a key for your (resulting in a random extension ID) or use an existing key (resulting in a known extension ID). More on that below. It is not possible to control the extension ID via `key` attribute in the `manifest.json` as you would do in the “load unpacked” flow.

### Packaging an app

Let's imagine you have built a Chrome app/extension at `/path/to/your/awesome_app` with `version: 4.2` in its `manifest.json`.

You can run the python script as following:
```
$ python3 update_local_extension_host.py <path_to_extension_directory_directory> [--extension_host_url <extension_host_url>] [--chrome_path <chrome_path>]
```
The arguments are:
* `path_to_extension_directory` - the path to your source directory containing the `manifest.json`, i.e. `/path/to/your/awesome_app`. In this case the final directory name `awesome_app` would be used as app identifier internally. This parameter is mandatory.
* `extension_host_url` - the URL to where your packaged extensions will be hosted from (see below). Optional, defaults to http://127.0.0.1:8888. If you plan to use the packed app on another device, you likely want to use your development machine's local IP address / hostname here instead.
* `chrome_path` - the path to the chrome binary that should be used for packaging. Optional, defaults to `google-chrome` (works on linux). On Windows/Mac, you need to update this parameter to your local Chrome's binary path.

The script will do the following:
1. Read the app's version from the manifest.json
2. Check if the app/extension (identified via directory name) has been served before / has a key. If not:
    1. Generate a new key and store it as `${EXTENSION_ID}.pem` in the `PEMs` directory
    2. insert mapping `${DIRECTORY_NAME}: ${EXTENSION_ID}` into `PEMs/ids.json`
    3. add an `<app>` item into `host/update_manifest.xml` 
3. Read the app's last served version from `hosts/update_manifest.xml`
4. Compute the new app version, i.e. `new_version = increase_minor_version(max(manifest_version, last_served_version))`. The initial `4.2` from our update manifest would then be `4.2.1`, then `4.2.2`, `4.2.3`, etc.
5. Temporarily upate the `version` and `update_url` fields in the `manifest.json` with the new version and given `extension_host_url`
6. Pack the app using `chrome_path` and the `--pack-extension=/path/to/your/awesome_app` argument
7. Move the packed `.crx` into the `hosts directory`
8. Update the `hosts/update_manifest.xml` to reflect the latest version and `.crx` file
9. Print out the extension ID and newly served version

#### Using an existing key
If you already have a private key (`.pem` file) and want the script to use that in order to receive the associated extension ID, simply move the `.pem` file into the `PEMs` directory named as `${EXTENSION_ID}.pem` and add an entry `${DIRECTORY_NAME}: ${EXTENSION_ID}` into `PEMs/ids.json`. Next time you run the script, it will use your given private key for signing the `.crx` file, which you can confirm by the logged extension ID at the end.

### Serving an app
In order to self-host the packed apps/extensions, they need to be available from your test device. We simply do so by hosting the `host` directory with a simple http server on a given port (e.g. 8888).
```
$ cd hosts
$ python3 -m http.server 8888 --bind 127.0.0.1
```
This process needs to be kept running. You can interrupt/cancel it with `CTRL+C` when done.

You can test that everything worked by navigating to [http://YOUR_LOCAL_IP_HERE:8888/update_manifest.xml](http://YOUR_LOCAL_IP_HERE:8888/update_manifest.xml), which should show you an XML document with an entry for your app/extension.

### Force-installing an app
#### Via Google admin console
Configure the [ExtensionInstallForcelist](https://chromeenterprise.google/intl/en_us/policies/#ExtensionInstallForcelist) to force-install the self-hosted and packaged app/extension by specifying the extension ID and insert URL to the `update_manifest.xml` ([http://YOUR_LOCAL_IP_HERE:8888/update_manifest.xml](http://YOUR_LOCAL_IP_HERE:8888/update_manifest.xml)) as `From custom URL`.

#### Via local policy file
To use this, your device must be in developer mode (see below), with rootfs verification removed (see below) and should not receive policy from anywhere else (otherwise `ExtensionInstallForcelist` would conflict on different sources).

On the device, open a shell (see below) and create a `policy.json` file in `/etc/opt/chrome/policies/managed` with the following contents:
```json
{
    "ExtensionInstallForcelist": ["${EXTENSION_ID};http://YOUR_LOCAL_IP_HERE:8888/update_manifest.xml"]
}
```

#### Verify 
The entry should show up as `["${EXTENSION_ID};http://YOUR_LOCAL_IP_HERE:8888/update_manifest.xml"]` on the device's [chrome://policy](chrome://policy) page then. You should also see the packed app/extension on the [chrome://extensions](chrome://extensions) page.

### Updating
Every time you want to test a code change to your app/extension, you would run the `update_local_extension_host` command and then go to the chromebook's [chrome://extensions](chrome://extensions) page and click the `Update` button. The device should pick up the latest version of the `.crx` immediately and show the updated version.

## Remote debugging
Typically, you would use [chrome://inspect](chrome://inspect) page to access the logs of your app/extension. When the app/extension now runs on a different device, you can still use the [chrome://inspect](chrome://inspect) page on that device or use the "remote debugging" explained here to access the developer tools of your testing device on your development device.

### On the test device (Chromebook)

#### Enter developer mode
> WARNING: This wipe all data on your device!
* Enter recovery mode first: Hold `ESC` + `Refresh` (`F2`) and press `Power`
* In recovery mode, press `CTRL+D` followed by `ENTER` to accept
* Wait for the device to enable developer mode
* In developer mode, the device will boot to a "developer mode warning" screen. Press `CTRL+D` to skip or wait
* More resources [here](https://chromium.googlesource.com/chromiumos/docs/+/HEAD/debug_buttons.md#Devices-With-Keyboards) and [here](https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_mode.md)

#### Sign in to shell
Requires a device in developer mode.
* Press `CTRL+ALT+Refresh (F2)`
* Login as `root` at `localhost login:` prompt (insert password if required, see below)
  
#### Remove rootfs verification
From shell:
* Run command: `sudo /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification`
* If the command does not succeed and it recommends running it with a `--partition` argument, copy the recommended command and run it again.
* Run command: `reboot`

#### Add debugging flags
From shell:
* Run commands:
    * `echo “--remote-debugging-port=9222” >> /etc/chrome_dev.conf`
    * `echo “--force-devtools-available” >> /etc/chrome_dev.conf`
    * `restart ui`

#### Enable SSH
From shell:
* Run command: `/usr/libexec/debugd/helpers/dev_features_ssh`
* Set password by running command `passwd`

#### Exit shell to return to CrOS GUI
From shell: 
* Press `CTRL+ALT+Back (F1)`

#### Get local IP address
* Click on the clock in bottom right corner to open quick settings
* Click on Ethernet/Wifi
* Click on `(i)` (top right corner)

### On the development device (Win/Mac/Linux)

#### Forward debugging port via SSH
* Run command `ssh -L 9222:localhost:9222 root@LOCAL_IP_ADDR_OF_YOUR_CHROMEBOOK_HERE`
* enter password configured via `passwd` before

#### Open debug tools
* Navigate to [chrome://inspect](chrome://inspect)
* You should now see the developer tools for all open tabs/apps/extensions from the test device (might take a second to load)
