import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import {getUrlParams, isEmbedded} from '@/util/browser'

import {GameHeader, AddChipsButton} from '@/poker/components/header.mobile'
import {SitDownButton} from '@/poker/components/header'
import {Board, DealerButton} from '@/poker/components/board.mobile'
import {Seat} from '@/poker/components/seat.mobile'
import {SeatCards} from '@/poker/components/cards.mobile'
import {SeatChips} from '@/poker/components/chips.mobile'
import {PassiveActions} from '@/poker/components/passive-actions.mobile'
import {Pot} from '@/poker/components/pot.mobile'
import {Chat} from '@/chat/components.mobile'
import {
    mapStateToProps,
    ForEachPosition,
    BackgroundLayer,
    FeltLayer,
    ActionsLayer,
    PreActionsLayer,
    confirmClose,
    tournamentHasFinished
} from '@/poker/components/layers'


export const HeaderLayer = () =>
    <div className="table-layer layer-header">
        <GameHeader/>
    </div>

export const AddChipsLayer = () =>
    <div className="table-layer layer-add-chips">
        <AddChipsButton />
    </div>

export const BoardLayer = () =>
    <div className="table-layer layer-board">
        <Board/>
    </div>

export const PassiveActionsLayer = () =>
    <div className="table-layer layer-passive-actions">
        <PassiveActions/>
    </div>

export const PotLayer = () =>
    <div className="table-layer layer-pot">
        <Pot/>
    </div>

export const SeatsLayer = () =>
    <ForEachPosition component={Seat} className="table-layer layer-seats"/>

export const CardsLayer = () =>
    <ForEachPosition component={SeatCards} className="table-layer layer-cards"/>

export const ChipsLayer = () =>
    <ForEachPosition component={SeatChips} className="table-layer layer-chips"/>

class MobileTablePanelComponent extends React.Component {
    componentDidMount() {
        if (this.props.logged_in_player && !isEmbedded()) {
            global.onbeforeunload = (e) => confirmClose(e)
        }
    }
    render() {
        const {className, gameVariantClass, logged_in_player, tournament} = this.props
        let layers = [
            <BackgroundLayer key="bg" />,
            <FeltLayer key="felt" />,
            <BoardLayer key="board" />,
            <PotLayer key="pot" />,
            <CardsLayer key="cards" />,
            <ChipsLayer key="chips" />,
        ]
        if (!tournamentHasFinished(tournament)) {
            layers = [
                ...layers,
                <SeatsLayer key="seats" />,
                <DealerButton key="dealer" />,
                <SitDownButton key="sit-down-table" mobile={true} />,
            ]
        }
        if (logged_in_player && !tournamentHasFinished(tournament)) {
            layers = [
                ...layers,
                <ActionsLayer key="actions" />,
                <PreActionsLayer key="pre-actions" />,
                <PassiveActionsLayer key="passive-actions" />,
            ]
        }

        return <div className="layers-container">
            <div className={classNames('table', 'table-layers', className, gameVariantClass)}>
                {layers || ''}
            </div>
            <HeaderLayer key="header" />
            <AddChipsLayer key="add-chips" />
            {getUrlParams(window.location.search).nochat ?
                null
                : <Chat />}
        </div>
    }
}

export const MobileTablePanel = reduxify({
    mapStateToProps,
    render: (props) =>
        <MobileTablePanelComponent {...props}/>
})
