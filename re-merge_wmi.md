# Re-merge WMI (twisted / django app in `licornd`)

* merge daemons
	* [OK] start
	* [OK] shutdown
	* dump_status

* what to do with collectors ?
	* [OK] they become just standard handlers, collected by the WMI app when it starts.
	* need a new decorator to re-inject the `request` argument, from the user queues, which are lost in standard events callbacks.

* recall core objets (without proxys)
