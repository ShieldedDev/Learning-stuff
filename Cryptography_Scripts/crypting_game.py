#!/bin/python3

from cryptography.fernet import Fernet

n_o = input("(N)ew or (O)ld: ")

if n_o.lower()=='n':
    key = Fernet.generate_key()
    print(key.decode())

elif n_o.lower()=='o':
    key = input("Enter key: ").encode()
    p_key = key
    print(p_key)

else:
    print("Entered the wrong option..")



def read():
    paste = input("Paste msg: ")
    paste = paste.encode()
    f = Fernet(key)
    msg = f.decrypt(paste)
    print("Decrypted messafe: ",msg)
    
    
def write():
    msg = input('Enter the msg: ')
    msg = msg.encode()
    f = Fernet(key)
    msg = f.encrypt(msg)
    print("Encrypted msg: ",msg)

while True:
    op = input("(R)ead or (W)rite or (Q)uit? : ")

    if op.lower()=='q':
        break
    elif op.lower()=='w':
        write()
    elif op.lower()=='r':
        read()
