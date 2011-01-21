.. _models:

Internal models in Licorn®
==========================

**Controllers**
	Holding unit objects at runtime and running high-level or mass operations on them.
	Giant lockable at controller level (thread-safe).
	Trigger backend/extension data load/save.

**Unit Object**
	Can be stored (in a backend) or not (thus volatile and lost at daemon shutdown).
	Locked at individual level (thread-safe).
	
**Backends**
	Linked to controllers when found compatible, and dedicated to unit objects storage.
	Able to lock the real storage, globally or finer, depending on the storage.
	Implement priorities between backends that are compatible with the same type of controller.
	
**Extensions**
	Add functionnality / attributes to Unit Objects.
	Can have their own storage, or store in the backend (extending LDAP schemata, depending on the type of the extension).
	
**CLIProxy** (yet named `RWI` but the name will change ASAP)
	Handle transformations from and to CLI tools, to leverage the amount of data incoming to and outgoing from the daemon. This speeds up networked operations (Pyro remote calls) a lot and offers a kind of shield in front of the Controllers and all other critical data.
