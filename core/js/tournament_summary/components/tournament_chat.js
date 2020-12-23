import React from 'react'

import Col from 'react-bootstrap/lib/Col'

import {Chat} from '@/chat/components.desktop'


export const TournamentChat = () =>
    <Col lg={4} md={4} sm={12} className='tournament-chat'>
        <h4>Chat</h4>
        <hr />
        <Chat is_tournament/>
    </Col>