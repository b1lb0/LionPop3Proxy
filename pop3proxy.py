#!/usr/bin/python
"""Vanbasten POP3 proxy server

Useage:
    python pop3proxy.py <host:port> <host:port>
"""
import logging
import os
import socket
import sys
import traceback
import re

logging.basicConfig(format="%(name)s %(levelname)s - %(message)s")
log = logging.getLogger("vanpopproxy")
log.setLevel(logging.INFO)

class manageConnection(object):
    END = "\r\n"
    def __init__(self, conn):
        self.conn = conn
    def __getattr__(self, name):
        return getattr(self.conn, name)
    def sendall(self, data, END=END):
        if len(data) < 50:
            log.debug("send: %r", data)
        else:
            log.debug("send: %r...", data[:50])
        data += END
        self.conn.sendall(data)
    def recvall(self, END=END):
        data = []
        while True:
            chunk = self.conn.recv(4096)
            if END in chunk:
                data.append(chunk[:chunk.index(END)])
                break
            data.append(chunk)
            if len(data) > 1:
                pair = data[-2] + data[-1]
                if END in pair:
                    data[-2] = pair[:pair.index(END)]
                    data.pop()
                    break
        log.debug("recv: %r", "".join(data))
        return "".join(data)

def Usage():
    print "USAGE: [-v] <local_host>:<local_port> <remote_host>:<remote_port>"

def handleCapa(data,rconn, verbose):
    return "+OK capability list follows\r\nUSER\r\nTOP\r\nUID\r\n."

def handleProxyNewline(data, rconn, verbose):
    rconn.sendall(data)
    if verbose: log.info("remote send: %r", "".join(data))
    response = rconn.recvall("\r\n.\r\n")+"\r\n."
    if verbose: log.info("remote receive: %s", response)
    return response

def handleProxy(data, rconn, verbose):
    rconn.sendall(data)
    if verbose: log.info("remote send: %r", "".join(data))
    response = rconn.recvall()
    if verbose: log.info("remote receive: %s", response)
    return response

def handleQuit(data,rconn, verbose):
    handleProxy(data, rconn, verbose)
    return "+OK Vanbasten POP3 Proxy server signing off"

def handleUidl(data,rconn, verbose):
    if re.compile('^UIDL [1-9]+').match(data):
        return handleProxy(data, rconn, verbose)
    else:
        return handleProxyNewline(data, rconn, verbose)

dispatch = dict(
    CAPA=handleCapa,
    LIST=handleProxyNewline,
    RETR=handleProxyNewline,
    UIDL=handleUidl,
    TOP=handleProxyNewline,
    QUIT=handleQuit,
)

def serve(host, port, hostr, portr, verbose):
    #local
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))

    try:
        log.info("Vanbasten POP3 Proxy server on %s:%s -> %s:%s", host, port, hostr, portr)

        while True:
            sock.listen(1)
            conn, addr = sock.accept()
            log.debug('Connected by %s', addr)
            
            #remote
            remotesock = socket.socket()
            if verbose: log.info("Making connection to %s:%s", hostr, portr)
            try:
                remotesock.connect((hostr, portr))
            except Exception, ex:
                continue
            try:
                rconn = manageConnection(remotesock)
                #Remote greetings clean
                data = rconn.recvall()

                conn = manageConnection(conn)
                conn.sendall("+OK Vanbasten POP3 Proxy server ready")
                while True:
                    data = conn.recvall()
                    if len(data) > 2:
                     try:
                        command = data.split(None, 1)[0]
                        cmd = dispatch[command]
                     except KeyError:
                        data = handleProxy(data, rconn, verbose)
                        conn.sendall(data)
                        #conn.sendall("-ERR unknown command")
                     else:
                        conn.sendall(cmd(data,rconn,verbose))
                        
                        if cmd is handleQuit:
                            break
            except Exception, ex:
                continue
            finally:
                rconn.close()
                conn.close()
    except (SystemExit, KeyboardInterrupt):
        log.info("Vanbasten POP3 stopped")
    except Exception, ex:
        log.critical("fatal error", exc_info=ex)
    finally:
        try:
                remotesock.shutdown(socket.SHUT_RDWR)
                rconn.close()

                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
        except:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        Usage()
    elif len(sys.argv)>2:
            verbose = False
            if len(sys.argv)==4:
                _, option, local, remote = sys.argv

                if option != "-v":
                        print "Bad ",option," parameters"
                        Usage()
                        exit(1)
                else:
                        verbose=True

            elif len(sys.argv)==3:
                _, local, remote = sys.argv

            if ":" in local and ":" in remote:
                host = local[:local.index(":")]
                port = local[local.index(":") + 1:]
                hostr = remote[:remote.index(":")]
                portr = remote[remote.index(":") + 1:]
        
                try:
                        port = int(port)
                        portr = int(portr)
                except Exception:
                        print "Bad port number:", port, portr
                else:
                        serve(host, port, hostr, portr, verbose)
            else:
                print "error : ",local
                Usage()
            
    else:
        Usage()
