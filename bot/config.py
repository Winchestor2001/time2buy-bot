from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
BACKEND_BASE_URL = env.str("BACKEND_BASE_URL")
WEBAPP_URL = env.str("WEBAPP_URL")
