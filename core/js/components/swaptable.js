import React from 'react'

import {reduxify} from '@/util/reduxify'
import {setResizeTable} from '@/util/browser'
import {windowResize} from '@/poker/reducers'

import {MobileTablePanel} from '@/poker/components/layers.mobile'
import {TablePanel} from '@/poker/components/layers.desktop'

export class SwapTableComponent extends React.Component {
    constructor(props) {
        super(props)
        this.state = {mobile: false, centered: false, desktop: true}
    }
    toMobile() {
        this.setState({
            ...this.state,
            mobile: true,
            centered: false,
            desktop: false
        })
        this.props.windowResize({resolution: 'mobile'})
    }
    toCenter() {
        this.setState({
            ...this.state,
            mobile: false,
            centered: true,
            desktop: false
        })
        this.props.windowResize({resolution: 'centered'})
        setResizeTable()
    }
    toDesktop() {
        this.setState({
            ...this.state,
            mobile: false,
            centered: false,
            desktop: true
        })
        this.props.windowResize({resolution: 'desktop'})
        setResizeTable()
    }
    componentDidMount() {
        const width = global.innerWidth
        if (width <= 767){
            this.toMobile()
        } else if (width <= 1200){
            this.toCenter()
        } else {
            this.toDesktop()
        }
        $(global).resize(() => {
            const width = global.innerWidth
            const to_mobile = width <= 767 && !this.state.mobile
            const to_center = 767 < width && width <= 1200 && !this.state.centered
            const to_desktop = width > 1200 && !this.state.desktop
            if (to_mobile) {
                this.toMobile()
            } else if (to_center) {
                this.toCenter()
            } else if (to_desktop) {
                this.toDesktop()
            }
        })
    }
    render() {
        return this.state.mobile ? <MobileTablePanel/> : <TablePanel/>
    }
}

export const SwapTable = reduxify({
    mapDispatchToProps: {
        windowResize
    },
    render: (props) =>
        <SwapTableComponent {...props}/>
})
