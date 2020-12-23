import React from 'react'
import {reduxify} from '@/util/reduxify'

import DropdownButton from 'react-bootstrap/lib/DropdownButton'
import MenuItem from 'react-bootstrap/lib/MenuItem'
import {tooltip} from '@/util/dom'
import {Icon} from '@/components/icons'

import {SocketStatus} from '@/websocket/components'

import {pauseBackend, nextAction} from '@/poker/debugging'
import {
    mapDispatchToProps,
    mapStateToProps,
    SitDownButton,
    ToggleSoundsClass
} from '@/poker/components/header'
import {
    TableInfoModalTrigger,
    ShareTableModalTrigger,
    ReportBugModalTrigger,
    HandHistoryModalTrigger,
    OneTimeBuyModalTrigger,
    AutoRebuyModalTrigger,
    PlayerWinningsModalTrigger
} from '@/poker/components/modals'


class ToggleSounds extends ToggleSoundsClass {
    render() {
        return <Icon name={`volume-${this.state.muted ? 'off' : 'up'} toggle-sounds`}
                     style={{cursor: 'pointer'}}
                     {...tooltip(`${this.state.muted ? 'Unmute' : 'Mute'} sounds`)}
                     onClick={() => this.onToggle()}/>
    }
}

export const GameHeader = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        return <header className="game-header">
            {/* Call-to-Action Buttons (top right) */}
            <SitDownButton/>

            {/* Table Name & Info (top left) */}
            <h2 style={{display: 'inline-block', marginTop: 10}}>
                {props.is_private && <Icon name='eye-slash' {...tooltip('Private Game')} />}&nbsp;
                {(global.user && props.table_locked) &&
                    (global.user.cashtables_level < props.bb ?
                        <Icon name='lock' {...tooltip('Earn more chips to unlock!')} />
                      : <a href="/accounts/email/" target="_blank">
                            <Icon name='lock' {...tooltip('Verify your email address to play')} />
                        </a>)
                }&nbsp;
                {props.name} &nbsp;&nbsp;
            </h2><br/>
            <small className="orange">
                {`${props.sb.toLocaleString()}/${props.bb.toLocaleString()} ${props.variant}
                 ${props.is_tournament ? '(tournament)' : '' }`}
            </small>&nbsp; &nbsp;
            <SocketStatus/>
            <ToggleSounds muted_sounds={props.muted_sounds}
                          onToggleSound={props.onToggleSound}/>
            <br/>
        </header>
    }
})


const RebuyMenu = ({bb, can_buy, can_set_auto_rebuy, title, num_seats,
                    min_buyin, max_buyin, player_auto_rebuy,
                    legal_min_buyin, legal_max_buyin, onSubmitAction}) =>
    <span id={`add-chips-${num_seats == 5 ? '5' : 'other'}-seats`}
          onClick={() => $('#rebuy-menu').next('.dropdown-menu').removeClass('fixed-on-seat')}>
        <DropdownButton id="rebuy-menu" title={title}>
            {can_buy ?
                <OneTimeBuyModalTrigger legal_min_buyin={legal_min_buyin}
                                        legal_max_buyin={legal_max_buyin}
                                        player_auto_rebuy={player_auto_rebuy}
                                        onSubmitAction={onSubmitAction}>
                    <MenuItem className="dropdown-item"
                            key="one-time-buy">
                        Add play-chips
                    </MenuItem>
                </OneTimeBuyModalTrigger>
                : <MenuItem className='dropdown-item'
                            key='one-time-buy'
                            disabled={true}
                            {...tooltip("You alredy have the max buyin for the table")}>
                        Add play-chips
                </MenuItem>}

            {can_set_auto_rebuy &&
                <AutoRebuyModalTrigger min_buyin={min_buyin}
                                       max_buyin={max_buyin}
                                       bb={bb}
                                       player_auto_rebuy={player_auto_rebuy}
                                       onSubmitAction={onSubmitAction}>
                    <MenuItem className="dropdown-item"
                              key="auto-rebuy">
                        Set auto rebuy...
                    </MenuItem>
                </AutoRebuyModalTrigger>}
            <small className="small-balance" {...tooltip('Total available balance in your play-chip wallet.')}>
                <a href={`/user/${global.user.username}`} target="_blank">Wallet: {Number(global.user.balance).toLocaleString()}㆔</a>
            </small>
        </DropdownButton>
    </span>

export const AddChipsButton = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        return !props.is_tournament && props.rebuy ?
            <RebuyMenu onSubmitAction={props.onSubmitAction}
                       title="Add Chips"
                       {...props.rebuy}/>
            : null
    }
})

export const TableOptionsButton = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) =>
        <DropdownButton bsStyle='default'
                        id="header-settings"
                        title="Options">

            <MenuItem key="game-info">
                <TableInfoModalTrigger table={props}>
                        <Icon name='bar-chart'/> Show Game Info
                </TableInfoModalTrigger>
            </MenuItem>

            {props.is_private &&
                <MenuItem key="show-player-winnings">
                    <PlayerWinningsModalTrigger>
                        <Icon name='money' />&nbsp; Show Player Winnings
                    </PlayerWinningsModalTrigger>
                </MenuItem>}

            <MenuItem key="show-hand-history">
                <HandHistoryModalTrigger>
                        <Icon name='file-text-o'/>&nbsp; Show Hand History
                </HandHistoryModalTrigger>
            </MenuItem>

            <MenuItem key="share-table-link">
                <ShareTableModalTrigger table={props}>
                        <Icon name='share-square'/>&nbsp; Share Table Link
                </ShareTableModalTrigger>
            </MenuItem>

            <MenuItem key="report-bug">
                <ReportBugModalTrigger>
                        <Icon name="comments-o"/>&nbsp; Talk to support
                </ReportBugModalTrigger>
            </MenuItem>
            {global.props.DEBUG &&
                <MenuItem key="pause"
                          onClick={pauseBackend}>
                    <Icon name="pause"/>&nbsp; Pause action
                </MenuItem>
                }
            {global.props.DEBUG &&
                <MenuItem key="nextaction"
                          onClick={nextAction}>
                    <Icon name="angle-double-right"/>&nbsp; Next action
                </MenuItem>
                }
        </DropdownButton>
    })
