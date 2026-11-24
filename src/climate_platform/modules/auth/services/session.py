"""Session lifecycle service: login/logout, session payload and demo accounts.

The controller only sets/clears the cookie and returns the response; authentication,
session rotation and the logout audit live here.
"""


class SessionService:
    def __init__(self, store, config):
        self.store = store
        self.config = config

    def payload(self, user, request_id):
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "csrf_token": user["csrf"],
            "demo": self.config.demo,
            "request_id": request_id,
        }

    def info(self):
        accounts = (
            [
                {
                    "username": name,
                    "password": account["password"],
                    "display_name": account["display_name"],
                    "role": account["role"],
                }
                for name, account in self.config.demo_accounts.items()
            ]
            if self.config.demo
            else []
        )
        return {"demo": self.config.demo, "demo_accounts": accounts}

    def login(self, ctx, username, password, old_token):
        token, _ = self.store.authenticate(username, password)
        if old_token:
            self.store.sessions.delete(old_token)
        user = self.store.session(token, self.config)
        return token, self.payload(user, ctx.request_id)

    def logout(self, ctx, user_id, token):
        self.store.sessions.delete(token)
        with self.store.db() as db:
            self.store.audit(db, user_id, "logout", None, request_id=ctx.request_id)

    def session(self, user, ctx):
        return self.payload(user, ctx.request_id)
