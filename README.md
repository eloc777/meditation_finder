# Meditation Group Finder

## Deployment (UQ Cloud Zone)

Live application URL:

[https://infs3202-7e53b724.uqcloud.net/meditationfinder/](https://infs3202-7e53b724.uqcloud.net/meditationfinder/)

## Environment variables (for markers)

To run locally, do the following.

1. Open the `**meditationfinder/**` folder that contains `**manage.py**` (inner project root).
2. Copy `**.env.example**` to `**.env**` in that same folder.
3. Set `**OPENAI_API_KEY**` in `**.env**` to the **course-provided** OpenAI key.
4. **Google Sign-In (optional for local runs):** this project used a **personal** OAuth client secret, which is **not** submitted. To test Google login locally you may either:
  - use the **live deployment** (which is already configured), or  
  - create your own **Web application** OAuth client in [Google Cloud Console](https://console.cloud.google.com/), add an **authorised redirect URI** matching the pattern documented in `**settings.py`** above `**SOCIALACCOUNT_PROVIDERS**`, put the matching `**GOOGLE_CLIENT_SECRET**` in `**.env**`, and — if your client ID differs from the one in `**settings.py**` — update `**SOCIALACCOUNT_PROVIDERS**` so **client ID** and **secret** belong to the **same** Google OAuth client.

Username/password login remains available regardless of Google configuration.

## Demo login accounts

These accounts are provided for markers

### Admin (staff — Django admin and full group-dashboard access)


| Field    | Value         |
| -------- | ------------- |
| Username | `Admin`       |
| Password | `changemepls` |


### Group manager (`group_manager` role on at least one listing)


| Field    | Value          |
| -------- | -------------- |
| Username | `Manager`      |
| Password | `changemealso` |


### General user


| Field    | Value             |
| -------- | ----------------- |
| Username | `Meditator`       |
| Password | `ilovemeditation` |


## Generative AI usage statement

**Cursor** was used as a day-to-day assistant across almost the whole lifecycle of the application: exploring how Django and django-allauth behave, drafting and adjusting models and migrations, shaping views and URL routing, building and iterating on Bootstrap templates, tracing permission and role behaviour, cleaning up retired or unused code paths, interpreting errors, and producing project documentation (including this README). In practice, it functioned like a pair-programmer and tutor for both small edits and larger refactors.

At each step I applied **critical judgment**: checking suggestions against my understanding and prompting further if I felt my understanding was lacking.