# Publishing a VidClips beta release

Do not commit the Windows installer `.exe` into the source tree. Keep the code in Git and attach the installer to a GitHub Release.

## One-time setup

1. Review and merge the draft pull request that adds the timeline, icon, and build workflow changes.
2. Open `tools/VidClips_Windows_Build.ipynb` in Google Colab.
3. Create a GitHub token scoped to this repository with **Actions: Read and write** and **Contents: Read-only**. Enter it only in the notebook's hidden prompt; never commit or paste it into a file.
4. Run the notebook only when you want a build. It triggers the Windows GitHub Actions runner, waits for the result, and downloads the `VidClips-Windows-Installer` artifact.

## Publish a beta

1. Test the downloaded installer on Windows 10, including importing a video with audio, seeing its waveform, running scene detection, checking cut positions, saving/opening a project, and launching the app from the installed shortcut.
2. In GitHub, open **Releases → Draft a new release**.
3. Create a new tag such as `v0.1.0-beta.1`. Use the exact source commit that was built and tested as the release target.
4. Set the title to **VidClips v0.1.0-beta.1**.
5. Attach the tested Windows installer `.exe` from the Colab download. Include a short description of known limitations and the Windows/Python requirements.
6. Check **Set as a pre-release** and publish the release.

For later beta builds, use incrementing tags such as `v0.1.0-beta.2`, then `v0.1.0-beta.3`. For a stable release, use a final version such as `v0.1.0` and leave the pre-release checkbox unchecked.

## Important

- The Windows build workflow is manual-only. A push or merge does not automatically create a new installer.
- Build first, test the installer, and only then publish the beta.
- The current installer packages the Python AI source and FFmpeg, but not the full Python runtime and every AI dependency. Users still need the documented Python 3.11/3.12 setup for local AI analysis.
- The Colab notebook triggers a Windows runner; Colab itself is Linux and should not be used to produce the native Windows installer directly.
