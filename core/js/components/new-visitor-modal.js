import React from 'react'

import Button from 'react-bootstrap/lib/Button'
import Modal from 'react-bootstrap/lib/Modal'

import {Icon} from '@/components/icons'

import {getUrlParams, localStorageGet, localStorageSet} from '@/util/browser.js'

let show_new_visitor_modal = false
const no_welcome = global.location && getUrlParams(global.location.search).nowelcome

if (!localStorageGet('first_visit') && !no_welcome) {
    localStorageSet('first_visit', Date.now())
    show_new_visitor_modal = true
}

const hideNewVisitorModal = () => {
    $('#new-visitor-modal').slideUp(() => {$('#new-visitor-modal').remove()})
    $('.modal-backdrop').remove()
}

export const NewVisitorModal = () => (
    show_new_visitor_modal ?
        <Modal aria-labelledby="contained-modal-title-sm" show id="new-visitor-modal" onClick={hideNewVisitorModal}>
            <Modal.Header>
                <Modal.Title id="contained-modal-title-sm" style={{fontFamily:'Bungee', textAlign: 'center'}}>
                    Welcome to Oddslingers Poker!
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <h4>Free, fast, secure online-poker that works on desktop &amp; mobile.</h4>
                <br/>
                There's currently a featured game in progress!<br/>
                <br/>
                You can watch the featured game, or:
                <ul>
                    <li>Go to the <a href="/tables">Play</a> page to start your own table</li>
                    <li>Go to the <a href="/leaderboard">Leaderboard</a> page to see who's crushing it</li>
                    <li>Go to the <a href="/learn">Learn</a> page if you need to learn the rules</li>
                </ul>
                Enjoy the festivities!
                <br/>
                <br/>
                <br/>
            </Modal.Body>
            <Modal.Footer>
                <img src="/static/images/coins.png" style={{width: '30%', float: 'left', marginTop: '-65px'}}/>
                <Button bsStyle="success" onClick={hideNewVisitorModal}>
                    Start Playing <Icon name="angle-double-right"/>
                </Button>
            </Modal.Footer>
        </Modal>
      : null)

// $('#welcome-modal').on('click', hideNewVisitorModal)
