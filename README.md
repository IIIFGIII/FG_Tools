![BTU title image](https://i.imgur.com/LqdCvL9.png)
BTU is simple tools inspired by [this script for 3Ds Max](http://www.scriptspot.com/3ds-max/scripts/3ds-max-to-ue4-fbx-scene-export) I used for all time I worked with Max as main modeling software. Now I swithched to Blender so I made similar tool for my self.

---------------------------------------------------------------------------------------------------------------------------------

Of course many diferent variations of " for Unreal " addons already exist. But most of them not contain instruments for copying objects to UE or (IMO) designed with some strange  " solutions ". So I started learn python to be able to make my own addon and here it is.

This addon designed to just work. You can just install, just select your objects and do batch export, then just copy objects to UE without touching any settings.

---------------------------------------------------------------------------------------------------------------------------------

# **Export FBX**

![export gif](https://i.imgur.com/IaINoJ2.gif)

Just batch exporter (another one). You can use it without touching any settings. But it has number of settings for custom purposes. **Take in to account that** I made it based on *my own usage experience*. 

It filter mesh objects only, etc. If you need a bit different settings - I hope you can easily change some export operator variables. I tried to write as possible clear to understand for " non coder " users (I even left fbx export operator defaults reminder inside).

# **Copy To UE** tool

![copy gif](https://i.imgur.com/ELcKlaP.gif)

It will copy objects names and transforms in specific format to buffer. Then if you paste it (`Ctrl + V`) in UE viewport - you will get objects with same names and transforms. It work pretty fast (in compare to 3D Max experience). Maximum I tried to copy 10 000 objects, it takse maybe ~ 2-3 seconds for copying to buffer (CPU Ryzen 3700x), then way more time to paste this 10 000 in to UE (3D Max experience - after ~ 300 objects things become toooooo sloooowwwwww, not even close to 2-3 seconds).

----------------------------------------------------------------------------------------------------------------------------------

Each item has small tultip. For detailed text description check **INFO** picture. Also watch [**demo video on youtube**](https://www.youtube.com/watch?v=RvydTKETguA). 
