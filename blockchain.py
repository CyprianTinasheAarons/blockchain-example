import hashlib
import json
import requests
from textwrap import dedent
from time import time
from uuid import uuid4
from flask import Flask , jsonify, request


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.nodes = set()
        self.current_transactions = []

        #genesis block
        self.new_block(previous_hash=1, proof=100)

    def register_node(self,address):

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        #creates a  new block and adds it to the chain
        block={
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
             'proof': proof,
             'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender ,recipient,amount):
        # adds a new transaction to the list of transactions
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })
        return self.last_block['index'] + 1
        

    @staticmethod
    def hash(block):
        #creates a SHA-256 hash of a block
        block_string = json.dumps(block,sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
        
    
    @property
    def last_block(self):
        #Returns the last block in the chain
        return self.chain[-1]

    def proof_of_work(self,last_block):
        """
        Simple Proof of Work Algorithm:
         - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
         - p is the previous proof, and p' is the new proof
        :param last_proof: <int>
        :return: <int>
        """
        proof = 0
        while self.valid_proof(last_block, proof) is False:
            proof += 1 

        return proof


    @staticmethod
    def valid_proof(last_proof ,proof):
        #Validates the Proof

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self , chain):
        # determine if a given blockchain is valid

        last_block =chain[0]
        current_index =1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n--------------\n")
            # check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            last_block = block
            current_index += 1

        return True
    
    def resolve_conflicts(self):

        neighbours = self.nodes
        new_chain =None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

#instantiate our Node
app = Flask(__name__)

#Generate a globally unique addres for this node
node_identifier = str(uuid4()).replace('-' ,'')

#instantiate the Blockchain
blockchain = Blockchain()

@app.route('/mine' , methods=['GET'])
def mine():
    # run proof of work algorithm to get the next proof...
    last_block = blockchain.last_block
    last_proof= last_block['proof']
    proof = blockchain.proof_of_work(last_proof)
    blockchain.new_transaction(
        sender="0",
        recipient = node_identifier,
        amount=1,
    )

    # forge the new block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof,previous_hash)

    response ={
        'message': 'New Block Forged',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response),200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json(force=True)
    
    required =['sender', 'recipient','amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    #Create a new transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response ={'message': f'Transaction will be added to Block{index}'}
    return jsonify(response), 201
    

@app.route('/chain', methods=['GET'])
def full_chain():
    response ={
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response),200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error:Please supply a valid list of nodes",400
    
    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response ={
            'message': 'Our chain is authoritative',
             'chain':blockchain.chain
        }

    return jsonify(response), 200
    
if __name__ == '__main__':
    app.run(debug=True)

