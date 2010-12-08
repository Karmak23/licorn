.. _cli:

Licorn® CLI (Command Line Interface)
====================================

The Licorn® CLI consists of five tools, used to manage the entire system:

**get**
	retrieve or display data
	
**add**
	add objects to the system
	
**mod**
	modify these objects, or the system configuration
	
**del** 
	delete objects from the system
	
**chk**
	check objects, paths, configuration, whatever can be, and repair interactively (or not).

All of them include integrated help if you call the program with argument `--help` (or `-h`) or if you make any mistake on the command line.

The logic behind the CLI is convention-driven, oriented towards extreme simplicity and maximum automatism, trying to provide maximum flexibility at the end-functionnality level. Understand that:

#. commands you type can be as small as possible, provided there is no ambiguity,
#. command-line flags are legions, but many of them are synonyms: *just pick the one that fits you best*,
