# Storage trust preview

Run `python trust/server.py` from a Git checkout and open the loopback address shown by the process. This is a standalone local preview, not integrated with the existing web application or a production deployment. Do not expose it to a network. It has no authentication, customer-data boundary, operational feed, incident source, or confirmed technical contact. It deliberately reports unavailable sources rather than manufacturing values.

Artifact downloads come exclusively from the checkout's committed HEAD, with content hashes verified before serving. The current library covers the capacity artifact directory only; it is not an inventory of other repository performance artifacts. The claim page references the existing audit, and shows the current token-scan outcome; the token scan does not discover all semantic claims. Do not interpret passing preview tests as product qualification or completed Phase B.

Run the end-to-end preview acceptance tests with `python -m unittest discover -s tests -p 'test_trust_preview.py' -v`.
