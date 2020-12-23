import React from 'react'
import distanceInWordsToNow from 'date-fns/distance_in_words_to_now'

import classNames from 'classnames'
import Alert from 'react-bootstrap/lib/Alert'

export class Notification extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            show: true,
            anim_ready: false,
        }
        this.waiting_notifications = [
            "wait_to_sit_in", "big_win", "true_grit", "player_eliminated",
            "tourney_winner"
        ]
    }
    onClose() {
        this.setState({
            ...this.state,
            show: false
        })
    }
    onAnimReady() {
        this.setState({
            ...this.state,
            anim_ready: true
        })
    }
    componentWillUpdate(nextProps) {
        const notif_ready = nextProps.notifications_ready === true
        if (notif_ready && !this.state.anim_ready) {
            this.onAnimReady()
        }
    }
    render() {
        const {notification, notifications_ready} = this.props
        const {
            ts,
            type,
            subtype,
            bsStyle,
            icon,
            url,
            title,
            description,
            noIcon,
            delay,
            redirect_url,
        } = notification
        const noClose = notification.noClose || this.props.noClose
        const need_animations = notification.type === "badge" ?
                                this.waiting_notifications.includes(notification.subtype)
                                : this.waiting_notifications.includes(notification.type)
        let showing = this.state.show
        if (showing && need_animations) {
            if (!this.state.anim_ready) {
                if (!notifications_ready){
                    showing = false
                }
            }
        }
        setTimeout(() => {
            if (!noClose && showing) {
                this.onClose()
            }
            if (redirect_url) {
                global.onbeforeunload = undefined
                global.location = redirect_url
            }
        }, delay || 8000)

        return showing ?
                <Alert bsStyle={bsStyle || 'info'}
                       className={classNames(`notification notification-${type || 'base'}`,
                                             `notification-${subtype || 'base'}`)}>
                    {!noClose &&
                        <span className="close" onClick={::this.onClose}>x</span>}
                    {!noIcon &&
                        <img className="icon" src={icon || '/static/images/info.svg'}/>}
                    <b className="title">{title}</b><br/>
                    {description ?
                        (url ?
                            <a className="description" href={url || '#'}>
                                {description}
                            </a>
                          :description)
                      : null}
                    {ts ?
                        <div style={{opacity: 0.8, fontSize: '0.8em', marginTop: 6}} className="timestamp">
                            {/* See: https://momentjs.com/docs/#/displaying/calendar-time/ */
                                distanceInWordsToNow(ts)
                            }
                        </div>
                      : null}
                </Alert>
                : null
    }
}
