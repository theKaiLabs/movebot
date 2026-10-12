"""Which add-on modules does this robot have?"""

from movebot import Bot

bot = Bot()

# --8<-- [start:list]
print("Plugged in:", bot.modules.ids())
for module in bot.modules:
    print(f"- {module.id}: a {module.type} sensor, values {module.value_names}")
    print("  reading now:", module.read())
# --8<-- [end:list]
