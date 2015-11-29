import os
import json
import binascii
import hashlib
import srvdb
import re
import base58
import ipaddress
import pprint
import time

# import flask web microframework
from flask import Flask
from flask import request
from flask import abort

# import from the 21 Developer Library
from two1.lib.bitcoin.txn import Transaction
from two1.lib.bitcoin.crypto import PublicKey
from two1.lib.wallet import Wallet, exceptions
from two1.lib.bitserv.flask import Payment

USCENT=2801

pp = pprint.PrettyPrinter(indent=2)

db = srvdb.SrvDb('turk.db')

app = Flask(__name__)
wallet = Wallet()
payment = Payment(app, wallet)

name_re = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")

def valid_name(name):
    if not name or len(name) < 1 or len(name) > 64:
        return False
    if not name_re.match(name):
        return False
    return True

@app.route('/domains')
def get_domains():
    try:
        domains = db.domains()
    except:
        abort(500)

    body = json.dumps(domains, indent=2)
    return (body, 200, {
        'Content-length': len(body),
        'Content-type': 'application/json',
    })

def parse_hosts(name, in_obj):
    host_records = []
    try:
        if (not 'hosts' in in_obj):
            return host_records

        hosts = in_obj['hosts']
        for host in hosts:
            rec_type = host['rec_type']
            ttl = int(host['ttl'])

            if ttl < 30 or ttl > (24 * 60 * 60 * 7):
                return "Invalid TTL"

            if rec_type == 'A':
                address = ipaddress.IPv4Address(host['address'])
            elif rec_type == 'AAAA':
                address = ipaddress.IPv6Address(host['address'])
            else:
                return "Invalid rec type"

            host_rec = (name, rec_type, str(address), ttl)
            host_records.append(host_rec)

    except:
        return "JSON validation exception"

    return host_records


def get_price_register(request):
    try:
        body = request.data.decode('utf-8')
        in_obj = json.loads(body)
        days = int(in_obj['days'])
    except:
        return 0
    if days < 1 or days > 365:
        return 0

    price = int(USCENT / 10) * days

    return price

@app.route('/host.register', methods=['POST'])
@payment.required(get_price_register)
def cmd_host_register():

    # Validate JSON body w/ API params
    try:
        body = request.data.decode('utf-8')
        in_obj = json.loads(body)
    except:
        return ("JSON Decode failed", 400, {'Content-Type':'text/plain'})

    try:
        if (not 'name' in in_obj):
            return ("Missing name", 400, {'Content-Type':'text/plain'})

        name = in_obj['name']
        pkh = None
        days = 1
        if 'pkh' in in_obj:
            pkh = in_obj['pkh']
        if 'days' in in_obj:
            days = int(in_obj['days'])

        if not valid_name(name) or days < 1 or days > 365:
            return ("Invalid name/days", 400, {'Content-Type':'text/plain'})
        if pkh:
            base58.b58decode_check(pkh)
            if (len(pkh) < 20) or (len(pkh) > 40):
                return ("Invalid pkh", 400, {'Content-Type':'text/plain'})
    except:
        return ("JSON validation exception", 400, {'Content-Type':'text/plain'})

    # Validate and collect host records for updating
    host_records = parse_hosts(name, in_obj)
    if isinstance(host_records, str):
        return (host_records, 400, {'Content-Type':'text/plain'})

    # Add to database.  Rely on db to filter out dups.
    try:
        db.add_host(name, days, pkh)
        if len(host_records) > 0:
            db.update_host(name, host_records)
    except:
        return ("Host addition rejected", 400, {'Content-Type':'text/plain'})

    body = json.dumps(True, indent=2)
    return (body, 200, {
        'Content-length': len(body),
        'Content-type': 'application/json',
    })

@app.route('/host.update', methods=['POST'])
@payment.required(int(USCENT / 3))
def cmd_host_update():

    # Validate JSON body w/ API params
    try:
        body = request.data.decode('utf-8')
        in_obj = json.loads(body)
    except:
        return ("JSON Decode failed", 400, {'Content-Type':'text/plain'})

    # Validate JSON object basics
    try:
        if (not 'name' in in_obj or
            not 'hosts' in in_obj):
            return ("Missing name/hosts", 400, {'Content-Type':'text/plain'})

        name = in_obj['name']
        if not valid_name(name):
            return ("Invalid name", 400, {'Content-Type':'text/plain'})
    except:
        return ("JSON validation exception", 400, {'Content-Type':'text/plain'})

    # Validate and collect host records for updating
    host_records = parse_hosts(name, in_obj)
    if isinstance(host_records, str):
        return (host_records, 400, {'Content-Type':'text/plain'})

    # Verify host exists, and is not expired
    try:
        hostinfo = db.get_host(name)
        if hostinfo is None:
            return ("Unknown name", 404, {'Content-Type':'text/plain'})
    except:
        return ("DB Exception", 500, {'Content-Type':'text/plain'})

    # Check permission to update
    pkh = hostinfo['pkh']
    if pkh is None:
        return ("Record update permission denied", 403, {'Content-Type':'text/plain'})
    sig_str = request.headers.get('X-Bitcoin-Sig')
    try:
        if not sig_str or not wallet.verify_bitcoin_message(body, sig_str, pkh):
            return ("Record update permission denied", 403, {'Content-Type':'text/plain'})
    except:
        return ("Record update permission denied", 403, {'Content-Type':'text/plain'})

    # Add to database.  Rely on db to filter out dups.
    try:
        db.update_host(name, host_records)
    except:
        return ("DB Exception", 400, {'Content-Type':'text/plain'})

    body = json.dumps(True, indent=2)
    return (body, 200, {
        'Content-length': len(body),
        'Content-type': 'application/json',
    })

@app.route('/task.new', methods=['POST'])
@payment.required(USCENT * 10)
def cmd_task_new():

    # Validate JSON body w/ API params
    try:
        body = request.data.decode('utf-8')
        in_obj = json.loads(body)
    except:
        return ("JSON Decode failed", 400, {'Content-Type':'text/plain'})

    # Validate JSON object basics
    try:
        if (not 'pkh' in in_obj or
            not 'image' in in_obj or
            not 'image_ctype' in in_obj or
            not 'questions' in in_obj or
            not 'min_workers' in in_obj or
            not 'reward' in in_obj):
            return ("Missing params", 400, {'Content-Type':'text/plain'})

        pkh = in_obj['pkh']
        image = binascii.unhexlify(in_obj['image'])
        image_ctype = in_obj['image_ctype']
        questions = in_obj['questions']
        min_workers = int(in_obj['min_workers'])
        reward = int(in_obj['reward'])

        base58.b58decode_check(pkh)
    except:
        return ("JSON validation exception", 400, {'Content-Type':'text/plain'})

    # Generate unique id
    time_str = str(int(time.time()))
    md = hashlib.sha256()
    md.update(time_str.encode('utf-8'))
    md.update(body.encode('utf-8'))
    id = md.hexdigest()

    # Add worker to database.  Rely on db to filter out dups.
    try:
        questions_json = json.dumps(questions)
        db.task_add(id, pkh, image, image_ctype, questions_json, min_workers, reward)
    except:
        return ("DB Exception - add task", 400, {'Content-Type':'text/plain'})

    body = json.dumps(True, indent=2)
    return (body, 200, {
        'Content-length': len(body),
        'Content-type': 'application/json',
    })

@app.route('/worker.new', methods=['POST'])
@payment.required(USCENT * 10)
def cmd_worker_new():

    # Validate JSON body w/ API params
    try:
        body = request.data.decode('utf-8')
        in_obj = json.loads(body)
    except:
        return ("JSON Decode failed", 400, {'Content-Type':'text/plain'})

    # Validate JSON object basics
    try:
        if (not 'payout_addr' in in_obj or
            not 'pkh' in in_obj):
            return ("Missing name/pkh", 400, {'Content-Type':'text/plain'})

        pkh = in_obj['pkh']
        payout_addr = in_obj['payout_addr']

        base58.b58decode_check(pkh)
        base58.b58decode_check(payout_addr)
    except:
        return ("JSON validation exception", 400, {'Content-Type':'text/plain'})

    # Add worker to database.  Rely on db to filter out dups.
    try:
        db.worker_add(pkh, payout_addr)
    except:
        return ("DB Exception - add worker", 400, {'Content-Type':'text/plain'})

    body = json.dumps(True, indent=2)
    return (body, 200, {
        'Content-length': len(body),
        'Content-type': 'application/json',
    })

@app.route('/')
def get_info():
    info_obj = {
        "name": "turk",
        "version": 100,
        "pricing": {
            "/worker.new" : {
               "minimum" : (USCENT * 10)
            },
        }

    }
    body = json.dumps(info_obj, indent=2)
    return (body, 200, {
        'Content-length': len(body),
        'Content-type': 'application/json',
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12007, debug=True)

