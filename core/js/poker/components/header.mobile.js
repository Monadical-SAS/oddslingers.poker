import React from 'react'
import {reduxify} from '@/util/reduxify'

import DropdownButton from 'react-bootstrap/lib/DropdownButton'
import MenuItem from 'react-bootstrap/lib/MenuItem'

import {Icon} from '@/components/icons'

import {pauseBackend, nextAction} from '@/poker/debugging'
import {
    mapDispatchToProps,
    mapStateToProps,
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
        return <MenuItem key="toggle-sounds"
                         onClick={() => this.onToggle() }>
            <Icon name={`volume-${this.state.muted ? 'off' : 'up'}`}/>&nbsp;
            {`${this.state.muted ? 'Unmute' : 'Mute'}`} sounds
        </MenuItem>
    }
}


export const GameHeader = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        return <header className="game-header">
            <DropdownButton bsStyle='default'
                            id="header-settings"
                            title="Options">

                <MenuItem key="game-info">
                    <TableInfoModalTrigger table={props}>
                            <Icon name='bar-chart'/>
                            Game Info
                    </TableInfoModalTrigger>
                </MenuItem>

                {props.is_private &&
                    <MenuItem key="show-player-winnings">
                        <PlayerWinningsModalTrigger>
                            <Icon name='money' /> Show Player Winnings
                        </PlayerWinningsModalTrigger>
                    </MenuItem>}

                <MenuItem key="show-hand-history">
                    <HandHistoryModalTrigger>
                            <Icon name='file-text-o'/> Show Hand History
                    </HandHistoryModalTrigger>
                </MenuItem>

                <MenuItem key="share-table-link">
                    <ShareTableModalTrigger table={props}>
                            <Icon name='share-square'/> Share Table Link
                    </ShareTableModalTrigger>
                </MenuItem>

                <MenuItem key="report-bug">
                    <ReportBugModalTrigger>
                            <Icon name='bug'/> Report a Bug
                    </ReportBugModalTrigger>
                </MenuItem>
                <ToggleSounds muted_sounds={props.muted_sounds}
                              onToggleSound={props.onToggleSound}/>

                {global.props.DEBUG &&
                    <MenuItem key="pause"
                              onClick={pauseBackend}>
                        <Icon name="pause"/> Pause action
                    </MenuItem>
                    }
                {global.props.DEBUG &&
                    <MenuItem key="nextaction"
                              onClick={nextAction}>
                        <Icon name="angle-double-right"/> Next action
                    </MenuItem>
                    }
            </DropdownButton>
        </header>
    }
})

const RebuyMenu = ({bb, can_buy, can_set_auto_rebuy, title,
                    min_buyin, max_buyin, player_auto_rebuy,
                    onSubmitAction}) =>

    <DropdownButton id="rebuy-menu" title={title}>
        {can_buy &&
            <OneTimeBuyModalTrigger min_buyin={min_buyin}
                                    max_buyin={max_buyin}
                                    player_auto_rebuy={player_auto_rebuy}
                                    onSubmitAction={onSubmitAction}>
                <MenuItem className="dropdown-item"
                          key="one-time-buy">
                    Add chips
                </MenuItem>
            </OneTimeBuyModalTrigger>}

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
    </DropdownButton>


export const AddChipsButton = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        return !props.is_tournament && props.rebuy ?
            <RebuyMenu onSubmitAction={props.onSubmitAction}
                       title="Chips"
                       {...props.rebuy}/>
            : null
    }
})