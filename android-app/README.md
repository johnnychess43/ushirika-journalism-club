# Ushirika Journalism Club — Android app

This is a separate Android app project. It opens the live Flask member portal at
https://ushirika-journalism-club-flask.onrender.com/login and keeps sign-in, registration,
articles, events, forums, gallery and payment flows connected to the same online service.

## Build an installable APK

1. Open the repository's **Actions** tab on GitHub.
2. Select **Build Ushirika Android app** and click **Run workflow** if it has not started automatically.
3. Open the completed run and download the `ushirika-android-builds` artifact.
4. Extract the ZIP and install the `app-debug.apk` on your Android phone. Android may ask you to allow installation from that source.

The debug APK uses application ID `org.ushirika.journalismclub.debug`. It can be installed for testing and is not the Play Store release.

## Google Play release

Google Play requires a properly signed release Android App Bundle (AAB), store listing, privacy policy, content declarations and review. The workflow also produces a release AAB, but it is **not Play-uploadable until it is signed with your upload key**.

Before a public release:
- Create an Android upload keystore and keep a secure backup.
- In **Settings → Secrets and variables → Actions**, add these repository secrets:
  - `ANDROID_KEYSTORE_BASE64`: the upload keystore file encoded as Base64
  - `ANDROID_KEYSTORE_PASSWORD`: keystore password
  - `ANDROID_KEY_ALIAS`: upload key alias
  - `ANDROID_KEY_PASSWORD`: upload key password
- Never commit the keystore or passwords. If signing secrets are absent, the workflow's AAB is unsigned and cannot be uploaded to Play Console.
- Review the app's privacy policy and ensure it accurately describes account data, uploaded media and payment-related data.
- Test login, registration, uploads, logout, external links and different screen sizes on real devices.
- Complete the Google Play Console developer registration and app review process.

The app requires an internet connection because the member portal and account data are hosted online. Private member and financial pages are not designed for offline caching.
