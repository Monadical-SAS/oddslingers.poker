import React from 'react'
import {reduxify} from '@/util/reduxify'

import {localStorageGet, localStorageSet} from '@/util/browser'

import {mapStateToProps} from '@/tournament_summary/components/shared'


class TournamentRedirectComponent extends React.Component {
    constructor(props) {
        super(props)
        const countdown = this.props.remaining_countdown.cd > 0 ?
            this.props.remaining_countdown.cd
            : 5
        this.state = {countdown}
    }
    updateCountdown() {
        const {countdown} = this.state
        this.setState({countdown: countdown - 1})
        const tournament_cd = {
            id: this.props.tournament_id,
            cd: countdown - 1
        }
        localStorageSet('tournament_redirect_countdown', tournament_cd)
    }
    componentDidMount() {
        this.interval = setInterval(::this.updateCountdown, 1000)
    }
    componentWillUnmount() {
        clearInterval(this.interval)
    }
    render() {
        const {countdown} = this.state
        if (countdown === 0) {
            localStorageSet('tournament_redirect_countdown', {})
            global.location = this.props.table_path
        }
        return <div role="dialog" className="tournament-redirect-countdown">
            <div className="fade modal-backdrop in"></div>
            <div role="dialog" tabIndex="-1" className="fade in modal" style={{"display": "block"}}>
                <div className="modal-dialog">
                    <h1 className="oddslingers-text-logo">
                        Tournament will start in<br/>
                        {countdown >= 0 ? countdown : 0}
                    </h1>
                </div>
            </div>
        </div>
    }
}

const shouldRedirect = (tournament_id, tournament_status, remaining_countdown,
                        is_entrant, redirect_to_table) => {

    const there_is_remaining_cd = remaining_countdown &&
        remaining_countdown.id === tournament_id &&
        remaining_countdown.cd > 0

    return there_is_remaining_cd || (is_entrant && redirect_to_table)
}

export const TournamentRedirect = reduxify({
    mapStateToProps,
    render: ({id, redirect_to_table, table_path, is_entrant, tournament_status}) => {
        const remaining_countdown = localStorageGet('tournament_redirect_countdown') || {}
        if (shouldRedirect(id, tournament_status, remaining_countdown,
                           is_entrant, redirect_to_table)) {
            return <TournamentRedirectComponent table_path={table_path}
                                                tournament_id={id}
                                                remaining_countdown={remaining_countdown}/>
        }
        return null
    }
})