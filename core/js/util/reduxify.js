import {connect} from 'react-redux'

export const reduxify = (container) =>
    connect(
        container.mapStateToProps,
        container.mapDispatchToProps,
    )(container.render)