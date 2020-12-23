import React from 'react'
import {reduxify} from '@/util/reduxify'

import Col from 'react-bootstrap/lib/Col'

import {Icon} from '@/components/icons'
import {chipAmtStr} from '@/util/javascript'
import {mapStateToProps} from '@/tournament_summary/components/shared'


export const TournamentResults = reduxify({
    mapStateToProps,
    render: ({tournament_status, results}) => {
        let first, second, third = {}
        if (results) {
            first = results.find(result => result.placement === 1)
            second = results.find(result => result.placement === 2)
            third = results.find(result => result.placement === 3)
        }

        if (tournament_status === 'FINISHED') {
            return <Col lg={4} md={4} sm={12} className="tournament-current-status">
                <h4>Results</h4>
                <hr/>
                <div className='tournament-podium'>
                    <div className='second'>
                        <Icon name='trophy'
                            text={<span className='podium-position'>2</span>}/>
                        <div className='player-name'>
                            {second.user}
                        </div>
                        {Number(second.payout_amt) > 0 &&
                            <div className='chips-amt'>
                                {chipAmtStr(second.payout_amt)}
                                <img className='chips-icon' src="/static/images/chips.png" title=""/>
                            </div>}
                    </div>
                    <div className='first'>
                        <Icon name='trophy'
                            text={<span className='podium-position'>1</span>}/>
                        <div className='player-name'>
                            {first.user}
                        </div>
                        <div className='chips-amt'>
                            {chipAmtStr(first.payout_amt)}
                            <img className='chips-icon' src="/static/images/chips.png" title=""/>
                        </div>
                    </div>
                    {third && <div className='third'>
                        <Icon name='trophy'
                            text={<span className='podium-position'>3</span>}/>
                        <div className='player-name'>
                            {third.user}
                        </div>
                        {Number(third.payout_amt) > 0 &&
                            <div className='chips-amt'>
                                {chipAmtStr(third.payout_amt)}
                                <img className='chips-icon' src="/static/images/chips.png" title=""/>
                            </div>}
                    </div>}
                </div>
            </Col>
        }
        return null
    }
})
