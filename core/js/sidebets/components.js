import React from 'react'
import classNames from 'classnames'

import Button from 'react-bootstrap/lib/Button'

import {Icon} from '@/components/icons'
import {tooltip} from '@/util/dom'

import {SidebetModalTrigger, ChangeSidebetModalTrigger} from '@/sidebets/modals'


export const NewSidebetModalButton = (props) =>
    <SidebetModalTrigger {...props}>
        <Button>
            <Icon name="dollar" id='sidebet-trigger' {...tooltip("Sidebet Info")}/>
        </Button>
    </SidebetModalTrigger>


export class ChangeSidebetModalButton extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            current_value: props.current_value,
            value_class: props.value_class
        }
    }
    componentWillUpdate(nextProps, nextState) {
        if (nextState == this.state){
            if (nextProps.animation_ends
                && nextProps.current_value != this.state.current_value) {
                this.setState({current_value: nextProps.current_value,
                               value_class: nextProps.value_class})
            }
        }
    }
    render() {
        return <ChangeSidebetModalTrigger {...this.props}>
            <Button className='change-bet-btn sidebet-value'>
                <b className={classNames(this.props.value_class)}>
                    {this.state.current_value.toFixed(3)}
                </b>
            </Button>
        </ChangeSidebetModalTrigger>
    }
}
