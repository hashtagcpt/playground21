
turk - Mechanical Turk service
==============================

WARNING:  Incomplete work-in-progress.

Summary:  API for automating and comparing work by human(?) workers.

Status:  Missing final compare-work-and-perform-payouts step.  All else works.


First time setup
----------------

	$ ./mkdb.sh

Running the server
------------------

	$ python3 turk-server.py



API
===

1. List DNS domains
-------------------
Show DNS domains, e.g. "example.com", available for use at this service.

HTTP URI: GET /domains

Params:

	None

Result:

	application/json document with the following data:
	List of domains (string)
	(or an HTTP 4xx, 5xx error)

Pricing:

	Free



2. Register host name
---------------------
HTTP URI: POST /host.register

Params:

	In HTTP body, a application/json document containing the following keys:

	name: name to register. Must be valid DNS name.
	pkh: (optional) public key hash for permissioned updates
	days: (optional) number of days to keep name registered (1-365)
	hosts: (optional) list of objects whose keys are:
		ttl: DNS TTL, in seconds
		rec_type: DNS record type ('A' and 'AAAA' supported)
		address: IPv4 or IPv6 address

Result:

	application/json document with the following data: true
	(or an HTTP 4xx, 5xx error)

Pricing:

	US$0.001/day



3. Update host records
----------------------
Replace _all_ DNS records associated a host, with the specified list.  An
empty list deletes all records.

HTTP URI: POST /host.update

Params:

	In HTTP body, a application/json document containing the following keys:

	name: name to register. Must be valid DNS name.
	pkh: public key hash for permissioned updates
	hosts: (optional) list of objects whose keys are:
		ttl: DNS TTL, in seconds
		rec_type: DNS record type ('A' and 'AAAA' supported)
		address: IPv4 or IPv6 address

	Header X-Bitcoin-Sig contains signature of encoded json document.

Result:

	application/json document with the following data: true
	(or an HTTP 4xx, 5xx error)

Pricing:

	US$0.0033



4. Delete host
--------------
Remove _all_ DNS records associated a host, as well as the host itself.

HTTP URI: POST /host.delete

Params:

	In HTTP body, a application/json document containing the following keys:

	name: name to register. Must be valid DNS name.
	pkh: public key hash for permissioned updates

	Header X-Bitcoin-Sig contains signature of encoded json document.

Result:

	application/json document with the following data: true
	(or an HTTP 4xx, 5xx error)

Pricing:

	Free




PUT /task.new

	Params:
		URL - POST result to
		image
		image content-type
		questions
		threshold of workers needed to complete task
		total reward, to be shared amongst all workers

GET /task

	Params:
		auth pubkey

	Result:
		json docu containing image, content-type, questions

PUT /task

	Params:
		auth pubkey
		answers

	Result:
		receipt for work submitted

PUT /worker.new

	Params:
		auth pubkey
		payout address
