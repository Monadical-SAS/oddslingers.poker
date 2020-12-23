import React from 'react'
import parse from 'date-fns/parse'
import differenceInSeconds from 'date-fns/difference_in_seconds'

import Button from 'react-bootstrap/lib/Button'
import Modal from 'react-bootstrap/lib/Modal'

import {Icon} from '@/components/icons'


// display modal if user was created less than 15sec ago
let is_new_user = false
if (global.user && global.user.date_joined) {
    const joined_seconds_ago = differenceInSeconds(Date.now(), parse(global.user.date_joined))
    is_new_user = joined_seconds_ago < 15
}

const hideWelcomeModal = () => {
    $('#welcome-modal').slideUp(() => {$('#welcome-modal').remove()})
    $('.modal-backdrop').remove()
}

export const WelcomeModal = () => (
    is_new_user ?
        <Modal bsSize="small" aria-labelledby="contained-modal-title-sm" show id="welcome-modal" onClick={hideWelcomeModal}>
            <Modal.Header>
                <Modal.Title id="contained-modal-title-sm" style={{fontFamily:'Bungee'}}>
                    Welcome to Oddslingers!
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <h4>You've been given {Number(global.page.props.SIGNUP_BONUS).toLocaleString()} chips!</h4>
                <br/>
                <p>Feel free to join the featured game, or create a new table and start a game of your own!</p>
                <br/>
                <p>You can find people to play with under the <a href="/leaderboard/">Leaderboard</a> tab, and see active tables under the <a href="/tables/">Poker Tables</a> tab.</p>
                <br/><br/>
            </Modal.Body>
            <Modal.Footer>
                <picture>
                    <source srcSet="/static/images/coins.webp" type="image/webp"/>
                    <img src="/static/images/coins.png" style={{width: '30%', float: 'left', marginTop: '-65px'}}/>
                </picture>
                <Button bsStyle="success" onClick={hideWelcomeModal}>
                    Start Playing <Icon name="angle-double-right"/>
                </Button>
            </Modal.Footer>
        </Modal>
      : null)

// $('#welcome-modal').on('click', hideWelcomeModal)
