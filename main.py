import discord
from discord.ext.commands import Bot
import asyncio
import os
from config import TOKEN, DATAFILE

lock = asyncio.Lock()
prefix = '/'

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = Bot(command_prefix = prefix, help_command = None, intents = intents)

@bot.event
async def on_ready():
	print(f'We have logged in as {bot.user}')
	print("Loading guild info...")
	bot.allowed_channels = dict()
	await lock.acquire()
	try:
		with open(DATAFILE) as guilds:
			for line in guilds.readlines():
				guild_id, back_channel_id, role_id = line.strip().split("; ")
				bot.allowed_channels[int(guild_id)] = (int(back_channel_id), int(role_id))
	except FileNotFoundError:
		newfile = open(DATAFILE, 'x')
		newfile.close()
	except:
		print("Opening the datafile failed for an unknown reason.")
		exit(1)
	lock.release()
	print("Loaded!")

@bot.event
async def on_member_update(before, after):
	guild = after.guild
	role = guild.get_role(bot.allowed_channels[guild.id][1])
	if role in after.roles and role not in before.roles:
		dm_channel = await bot.create_dm(after)
		await dm_channel.send(f"Hello! You've added the {role.name} role in {guild.name}. That means you can now exchange anonymous messages with other people who have this role by typing `/send <username> <message>`. For more details, type `/help`.")

@bot.command()
async def help(ctx):
	await ctx.send("Send messages through me using the `/send` command. For example, you could DM me `/send colopop Thanks for making this cool robot!` and I would DM the user `colopop` the message `Thanks for making this cool robot!`.\n" + 
		     "You can use the recipient's discord username or their server nickname; I'll recognize either. If their nickname is two or more words, wrap it in quotation marks: `/send \"Courier Bot\" Have a great day, my digital friend.`\n" +
		     "Unwanted messages can be reported simply by typing `/report`. You are always welcome to contact server moderators directly as well. They are able to see the message log and will take action as appropriate.")

@bot.command()
async def send(ctx, *args):
	print('received SEND command')
	if len(args) < 2:
		return

	recipient_name = args[0].lower()
	if recipient_name[0] == '@':
		recipient_name = recipient_name[1:]
	message = " ".join(args[1:])

	#figure out what server this is supposed to be posted in
	guild = None
	print(ctx.author.mutual_guilds)
	if len(ctx.author.mutual_guilds) == 1:
		guild = ctx.author.mutual_guilds[0]
	else:
		await ctx.send(f'Which of these servers do you want to send this to? {", ".join(str(i+1)+". "+g.name for i, g in enumerate(ctx.author.mutual_guilds))} [Please type the number corresponding to your choice.] ')
		i = int(await bot.wait_for('message', check = lambda x: x.author == ctx.author and x.channel == ctx.channel))
		try:
			guild = ctx.author.mutual_guilds[i-1]
		except:
			guild = ctx.author.mutual_guilds[0]


	if guild is not None:
		if guild.id not in bot.allowed_channels:
			await ctx.send(f"I'm not set up to send messages to {guild.name}. Sorry!")
			return
		
		#get member
		role = await guild.fetch_role(bot.allowed_channels[guild.id][1])
		#check usernames, then display names, then global names
		sender = next((member for member in role.members if member.name.lower() == ctx.author.name.lower()), 
			next((member for member in role.members if member.display_name.lower() == ctx.author.name.lower()), 
			next((member for member in role.members if member.global_name.lower() == ctx.author.name.lower()), 
			None)))
		
		if sender is None:
			await ctx.send(f"You need the \"{role.name}\" role in order to send messages through me.")
			return

		#check usernames, then display names, then global names
		recipient = next((member for member in role.members if member.name.lower() == recipient_name), 
			next((member for member in role.members if member.display_name.lower() == recipient_name), 
			next((member for member in role.members if member.global_name.lower() == recipient_name), 
			None)))
		
		if recipient is None:
			await ctx.send(f"I can't send a message to {recipient_name}. Make sure you've spelled their username right (if it's multiple words, wrap it in quotes) and that they have the `{role.name}` role in {guild.name}.")
			return


		new_dm = await bot.create_dm(recipient)
		await new_dm.send(f"📨 Somebody from {guild.name} sent you a message!\n\n{message}\n\n-# If this message was unwanted or inappropriate, type `/report` or contact a moderator.")

		if ctx.guild is None:
			await ctx.send("Sent! 📨")
		else:
			await ctx.message.delete()

		#log
		back_channel = bot.allowed_channels[guild.id][0]
		await (guild.get_channel(back_channel)).send(f'**FROM**: {ctx.author.name} **TO**: {recipient} **MESSAGE**: {message}')

@bot.command()
@discord.ext.commands.has_permissions(manage_messages=True, manage_roles=True)
async def setup(ctx, *, role_name):
	print("Received SETUP command")
	if ctx.guild is None:
		await ctx.send("You can't use /setup in DMs because I can't see which threads I'm supposed to post to. Try again in your server, using the syntax `/setup [role name]` in the mod channel of your choice.")
		return
	#try:
	channels = ctx.message.channel_mentions
	if len(channels) == 0:
		back_channel = ctx.channel
	elif len(channels) == 1:
		back_channel = channels[0]
	async with lock:
		try:
			role = await ctx.guild.fetch_role(bot.allowed_channels[ctx.guild.id][1])
		except:
			role = await ctx.guild.create_role()
		role = await role.edit(name=role_name)
		bot.allowed_channels[ctx.guild.id] = (back_channel.id, role.id)
	await update_guild_data(bot)
	await ctx.send(f"I'm now configured to log messages to #{back_channel.name} for moderation. Users with the \"{role_name}\" role can send and receive messages through me. You can reconfigure me at any time.")
	#except:
	#	await ctx.send("Something didn't work. Please try again.")

@bot.command()
async def report(ctx):
	print("received REPORT command")

	#figure out what server this is supposed to be reported to
	guild = None
	print(ctx.author.mutual_guilds)
	if len(ctx.author.mutual_guilds) == 1:
		guild = ctx.author.mutual_guilds[0]
	else:
		await ctx.send(f'Which of these servers do you want to send this report to? {", ".join(str(i+1)+". "+g.name for i, g in enumerate(ctx.author.mutual_guilds))} [Please type the number corresponding to your choice.] ')
		i = int(await bot.wait_for('message', check = lambda x: x.author == ctx.author and x.channel == ctx.channel))
		try:
			guild = ctx.author.mutual_guilds[i-1]
		except:
			guild = ctx.author.mutual_guilds[0]

	#log
	back_channel = bot.allowed_channels[guild.id][0]
	await (guild.get_channel(back_channel)).send(f'🚨 {ctx.author.name} has reported that the most recent message they received was unwanted. Please consult the logs and take appropriate action.')

	await ctx.send("Your report has been logged. A moderator will reach out to you soon.")


async def update_guild_data(bot):
	print("Updating stored data...")
	async with lock:
		with open(DATAFILE + "_NEW", "w") as newdata:
			for guild in bot.allowed_channels:
				newdata.write(f'{guild}; {"; ".join(str(i) for i in bot.allowed_channels[guild])}\n')
		os.remove(DATAFILE)
		os.rename(DATAFILE+"_NEW", DATAFILE)
	print("Updated!")

bot.run(TOKEN)