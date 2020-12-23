import React from 'react'

import Button from 'react-bootstrap/lib/Button'
import Modal from 'react-bootstrap/lib/Modal'

import {Icon} from '@/components/icons'


export class ModalTrigger extends React.Component {
    constructor(props, context) {
        super(props, context)
        this.state = {show: false}
        this.onKeyPressBound = ::this.onKeyPress
    }
    componentWillUnmount() {
        this.setState({show: false})
    }
    onKeyPress(e) {
        // confirm if they press enter (esc is handled automatically by Bootstrap)
        if (e.keyCode == 13) {
            this.onConfirm()
        }
    }
    onShow() {
        document.addEventListener('keypress', this.onKeyPressBound)
        this.setState({show: true})
    }
    onClose() {
        document.removeEventListener('keypress', this.onKeyPressBound)
        this.setState({show: false})
    }
    onConfirm(e) {
        this.onClose(e)
    }
    onCancel(e) {
        this.onClose(e)
    }
    render() {
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            {this.props.title}
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {this.props.body}
                    </Modal.Body>
                    <Modal.Footer>
                        <Button onClick={::this.onCancel}>
                            Cancel
                        </Button>
                        <Button bsStyle="success" onClick={::this.onConfirm}>
                            Ok &nbsp;<Icon name="check"/>
                        </Button>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}
