# Switchboard

A small SSH chat server built with Python. I wanted to make something simple that multiple people can use over the terminal, and so the most straightforward thing was to make a chat app.

## Features

The interface is super basic, there's no sections for different commands, settings or whatever, it's all just done from one line and everything is displayed as a scrolling transcript.

Some of the main things I implemented are:

- Open registration: anyone can join a pick an available name and make a password to access the chat.
- Multiple rooms: anyone can create and join rooms.
- Direct messages: you can DM another online user.
- Admin commands: kick, ban, announcements, clear message history.
- Input validation and rate limiting.

## Commands

Below are the commands available to every user:

| Command | Use |
| --- | --- |
| `/help` | List all commands |
| `/who` | List all connected members and their current rooms |
| `/rooms` | List public rooms, topics and user count |
| `/join [room]` | Join (or create) [room] |
| `/topic` | View current room's topic |
| `/history [1-100]` | View 1-100 previous messages |
| `/msg [user] [text]` | Send a DM to another online user |
| `/me [action]` | Post an action, e.g. "/me waves" |
| `/clear` | Clear the terminal |
| `/q` | Disconnect |

And these commands are only available to admins:

| Command | Use |
| --- | --- |
| `/topic [text]` | **ADMIN:** set current room's topic |
| `/kick [user]` | **ADMIN:** Disconnect another user |
| `/ban [user]` | **ADMIN:** Ban another user |
| `/unban [user]` | **ADMIN:** Unban another user |
| `/announce [text]` | **ADMIN:** Send a notice to every room |
| `/clearhistory confirm` | **ADMIN:** Permanently delete messages in the current room. |
| `/clearhistory [all] confirm` | **ADMIN:** Permanently delete messages from *all* rooms. |

## Account creation

Usernames have to be between 2 - 20 lowercase ASCII letters/digits/underscores/hyphens, and begin with a letter. You cannot change your username.
