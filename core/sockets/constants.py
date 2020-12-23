# special websocket message types used for managing the connection
# corresponds to constants at the top of websockets.js
HELLO_TYPE = 'HELLO'
GOT_HELLO_TYPE = 'GOT_HELLO'
PING_TYPE = 'PING'
PING_RESPONSE_TYPE = 'PING'
TIME_SYNC_TYPE = 'TIME_SYNC'
RECONNECT_TYPE = 'RECONNECT'
# use the value in this json field in the message to pick an
#   on_VALUE handler function
ROUTING_KEY = 'type'
