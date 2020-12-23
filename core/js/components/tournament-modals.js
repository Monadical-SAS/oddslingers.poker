import React from 'react'
import {reduxify} from '@/util/reduxify'

import Button from 'react-bootstrap/lib/Button'
import Modal from 'react-bootstrap/lib/Modal'

import {Icon} from '@/components/icons'

import {getGamestate} from '@/poker/selectors'
import {localStorageGet, localStorageSet} from '@/util/browser'
import {chipAmtStr} from '@/util/javascript'


class TournamentWinnerModal extends React.Component {
    constructor(props) {
        super(props)

        this.state = {
            show: true
        }
    }
    handleHide() {
        global.localStorage.removeItem(`show_result_modal_${this.props.tournament.id}`)
        const redirectToSummary = () => global.location = this.props.tournament.path
        this.setState({show: false}, redirectToSummary)
    }
    render() {
        return <Modal aria-labelledby="contained-modal-title-sm"
                      show={this.state.show}
                      id="welcome-modal"
                      onHide={::this.handleHide}>
            <Modal.Header>
                <Modal.Title id="contained-modal-title-sm" style={{ fontFamily: 'Bungee' }}>
                    Congratulations!
                </Modal.Title>
            </Modal.Header>
            <Modal.Body style={{textAlign: 'center'}}>
                <h4>You've won the tournament!</h4>
                <p>
                    An amount of {chipAmtStr(this.props.result.payout_amt)} chips has been transfered
                    to your balance, thanks for playing!
                </p>
                <img src="/static/images/coins.png" style={{ width: '20%'}} />
            </Modal.Body>
            <Modal.Footer>
                <Button bsStyle="success" onClick={::this.handleHide}>
                    Continue <Icon name="angle-double-right" />
                </Button>
            </Modal.Footer>
        </Modal>
    }
}

class TournamentLoserModal extends React.Component {
    constructor(props) {
        super(props)

        this.state = {
            show: true
        }
    }
    handleHide() {
        global.localStorage.removeItem(`show_result_modal_${this.props.tournament.id}`)
        this.setState({show: false})
    }
    getPlacementText() {
        const {placement} = this.props.result
        const suffixes = ['th', 'st', 'nd', 'rd']
        const v = placement % 100
        return placement + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0])
    }
    render() {
        return <Modal aria-labelledby="contained-modal-title-sm"
                      show={this.state.show}
                      id="welcome-modal"
                      onHide={::this.handleHide}>
            <Modal.Header>
                <Modal.Title id="contained-modal-title-sm" style={{ fontFamily: 'Bungee' }}>
                    You've finished the tournament in {this.getPlacementText()} place
                </Modal.Title>
            </Modal.Header>
            <Modal.Body style={{textAlign: 'center'}}>
                <h4>Thanks for Playing!</h4>
                <p>
                    {this.props.result === 2 ?
                        "You can still watch the rest of the tournament or go for another one!"
                        : "Try playing another one!"}
                </p>
            </Modal.Body>
            <Modal.Footer>
                <Button bsStyle="success" onClick={::this.handleHide}>
                    Continue <Icon name="angle-double-right" />
                </Button>
            </Modal.Footer>
        </Modal>
    }
}

export const TournamentResultModal = reduxify({
    mapStateToProps: (state) => {
        const {table} = getGamestate(state)
        const new_tourney_results = state.gamestate.new_tourney_results
        const tournament = table.tournament

        const player_results = new_tourney_results.filter(result =>
            global.user && result.user === global.user.username
        )

        // We are using the same notifications logic to sync the modal with the
        // WIN animation
        const modal_ready = table.badge_ready || false
        const result = player_results.length && player_results[0]
        if (modal_ready && result) {
            localStorageSet(`show_result_modal_${tournament.id}`, true)
        }

        return {tournament, player_results}
    },
    render: ({tournament, player_results}) => {
        if (tournament) {
            const result = player_results.length && player_results[0]
            const show_result_modal = localStorageGet(`show_result_modal_${tournament.id}`) || false
            if (show_result_modal && tournament && result) {
                return result.placement === 1 ?
                    <TournamentWinnerModal result={result} tournament={tournament}/>
                    : <TournamentLoserModal result={result} tournament={tournament}/>
            }
        }
        return null
    }
})
