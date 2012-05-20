.. _design:

Design and philosophy used in Licorn®
-------------------------------------

This document is quite a work in progress. Documenting the features and creating How-Tos is more important to us. But in a few words, the keypoints: 

* Final-user related:

	* offer as much functionnality as possible, without making the thing bloated (we refactor quite often)
	* don't take the user into proprietary or too complex mechanisms: Licorn® implements only well documented and known standards, and just sits on top of the system. If you wouldn't have it, you could achieve exactly the same work by hand (if you had an infinite life ;-) ).

* System Administrator related:

	* there is a distinction between a `standard` group and a `system` group:

		* a `standard` group has :

			* a special directory for its members to share data (files, documents, whatever)
			* 2 linked system groups, to hold responsibles and guests

	   * a `system` group has nothing of that kind, it is just a group
	   
			* it can be promoted to a privilege, which allows WMI administrators to add / del members (else WMI admins don't have access to any system groups).
      
* Code related:

	* Keep the code as simple as possible.
	* Keep the code as readable as possible.
	* Keep the code as maintainable as possible.

