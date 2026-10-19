# Connecting the robot

A MoveBot talks to your computer over Wi-Fi, in one of two ways. You choose, and you can
change your mind at any time.

| | **Its own Wi-Fi** (direct mode) | **Your Wi-Fi network** (network mode) |
|---|---|---|
| How | The computer joins the robot's network, `MoveBot-XXXX` | The robot joins the network the computer is on |
| Robot's address | always `192.168.4.1` | `movebot-xxxx.local`, or the address the setup shows |
| Internet on the computer | none while connected to the robot | yes |
| Works with any network | yes, it needs no network at all | only if the network lets devices talk to each other |
| Good for | classrooms, trips, anywhere | home, labs, school networks that allow it |

A new robot (or one reset to factory Wi-Fi settings) starts with **its own Wi-Fi**. The
password is printed on the robot.

!!! tip "Keep a way in"
    When the robot joins your network, it can **keep its own Wi-Fi on too**. That is the
    default, and the safest: if the network changes or blocks it, you can always connect to
    the robot directly and fix the settings. If it cannot join a network at all, it turns its
    own Wi-Fi back on by itself.

## In the MoveBot app

1. Connect to the robot: join its Wi-Fi (`MoveBot-XXXX`) on the computer, then press
   **Connect** at the top of the app and choose *MoveBot over Wi-Fi* (address `192.168.4.1`).
2. Open the same menu and press **Set up this robot…**.
3. Choose **Its own Wi-Fi** or **Your Wi-Fi network**. For a network: pick it from the list,
   type its password and press **Test the network**. The robot tries it while staying
   connected to you, so nothing breaks if the password is wrong.
4. Press **Save and restart**. The app tells you the robot's new address.

The same dialog renames the robot (handy when a class has 15 of them: its Wi-Fi gets the same
name), restarts it, and goes back to factory Wi-Fi settings.

!!! note "Practise with the simulator"
    The simulator has made-up networks to practise on: *Classroom* (password `robots123`),
    *School-Guest* (open), *eduroam* (needs a user name, which the robot cannot do) and
    *Home-2.4G*.

## From Python

Everything the app does is in the `movebot` library too:

```python
from movebot import Bot

bot = Bot()                               # e.g. on the robot's own Wi-Fi
print(bot.wifi.status())                  # how it is connected now

for network in bot.wifi.scan():           # what it can see
    print(network)                        # Classroom  ▮▮▮▮ (password)

result = bot.wifi.test("Classroom", "the password")   # try, without changing anything
print(result.joined, result.ip, result.message)

bot.wifi.join("Classroom", "the password")             # save it and restart the robot
bot.wifi.join("Classroom", "pw", keep_hotspot=False)   # ...and turn its own Wi-Fi off
bot.wifi.join("Lab", "pw", static_ip="192.168.10.20/24", gateway="192.168.10.1")

bot.wifi.hotspot()                        # back to only its own Wi-Fi
bot.wifi.hotspot(password="a new password")
bot.wifi.reset()                          # factory Wi-Fi settings

bot.rename("Rover 7", restart=True)
bot.restart()
```

`join()` tests the network first and raises `WifiJoinFailed` (with a `reason`) if it does
not work, so a typo never locks you out.

## From the command line

```bash
movebot wifi status
movebot wifi scan
movebot wifi join Classroom          # asks for the password
movebot wifi join Lab --static-ip 192.168.10.20/24 --gateway 192.168.10.1
movebot wifi hotspot --change-password
movebot wifi reset
movebot rename "Rover 7"
movebot restart
```

## When it does not work

| Problem | What to try |
|---|---|
| "No MoveBot found" on its own Wi-Fi | Is the computer connected to `MoveBot-XXXX`? Some computers leave a network without internet: tell it to stay connected. |
| The robot joined the network but the computer cannot reach it | The network may keep devices apart ("client isolation", common on school and guest networks). Use its own Wi-Fi instead, or ask IT. |
| `movebot-xxxx.local` is not found | Some networks block these names (mDNS). Use the address the setup showed, or give the robot a fixed address. |
| The network needs a user name and password (e.g. eduroam) | The robot cannot join those. Use its own Wi-Fi. |
| Nothing works any more | Connect to its own Wi-Fi (it comes back on if it cannot join), or hold the robot's button for 5 seconds for factory Wi-Fi settings. |

!!! warning "Passwords"
    Wi-Fi passwords travel only between this computer and the robot, and the robot never
    tells anyone a saved password. Do not put real passwords in programs you share.
