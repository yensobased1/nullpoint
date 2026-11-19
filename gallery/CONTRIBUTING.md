# Add your crosshair to the Nullpoint gallery

The **Gallery** tab in Nullpoint reads `gallery/index.json` from this repository. To add yours:

1. In Nullpoint, open **Share** and click **Copy Code** (the code starts with `XH3;`).
2. Fork this repository and edit `gallery/index.json`. Add one entry to `entries`:

   ```json
   {"name": "My Crosshair", "author": "your-github-name", "tags": ["tac-fps", "minimal"], "code": "XH3;..."}
   ```

   - `name` and `author`: up to 40 characters. `tags`: up to 8 short words.
   - `code`: exactly what Copy Code gave you. Image crosshairs aren't supported (codes hold settings only).
3. Open a pull request. Keep it to one or a few crosshairs, no offensive names.

Entries with an invalid code are ignored by the app, so please test your code with **Paste Code** first.
